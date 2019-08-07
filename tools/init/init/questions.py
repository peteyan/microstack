"""questions.py

All of our subclasses of Question live here.

We might break this file up into multiple pieces at some point, but
for now, we're keeping things simple (if a big lengthy)

----------------------------------------------------------------------

Copyright 2019 Canonical Ltd

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

 http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

"""


from time import sleep
from os import path

from init.shell import (check, call, check_output, shell, sql, nc_wait,
                        log_wait, restart, download)
from init.config import Env, log
from init.question import Question


_env = Env().get_env()


class ConfigError(Exception):
    """Suitable error to raise in case there is an issue with the snapctl
    config or environment vars.

    """


class Setup(Question):
    """Prepare our environment.

    Check to make sure that everything is in place, and populate our
    config object and os.environ with the correct values.

    """
    def yes(self, answer: str) -> None:
        """Since this is an auto question, we always execute yes."""
        log.info('Loading config and writing templates ...')

        log.info('Validating config ...')
        for key in ['ospassword', 'extgateway', 'extcidr', 'dns']:
            val = check_output('snapctl', 'get', key)
            if not val:
                raise ConfigError(
                    'Expected config value {} is not set.'.format(key))
            _env[key] = val

        log.info('Writing out templates ...')
        check('snap-openstack', 'setup')

        # Parse microstack.rc, and load into _env
        # TODO: write something more robust (this breaks on comments
        # at end of line.)
        mstackrc = '{SNAP_COMMON}/etc/microstack.rc'.format(**_env)
        with open(mstackrc, 'r') as rc_file:
            for line in rc_file.readlines():
                if not line.startswith('export'):
                    continue
                key, val = line[7:].split('=')
                _env[key.strip()] = val.strip()


class IpForwarding(Question):
    """Possibly setup IP forwarding."""

    _type = 'auto'  # Auto for now, to maintain old behavior.
    _question = 'Do you wish to setup ip forwarding? (recommended)'

    def yes(self, answer: str) -> None:
        """Use sysctl to setup ip forwarding."""
        log.info('Setting up ipv4 forwarding...')

        check('sysctl', 'net.ipv4.ip_forward=1')


class VmSwappiness(Question):

    _type = 'binary'
    _question = 'Do you wish to set vm swappiness to 1? (recommended)'

    def yes(self, answer: str) -> None:
        # TODO
        pass


class FileHandleLimits(Question):

    _type = 'binary'
    _question = 'Do you wish to increase file handle limits? (recommended)'

    def yes(self, answer: str) -> None:
        # TODO
        pass


class RabbitMQ(Question):
    """Wait for Rabbit to start, then setup permissions."""

    def _wait(self) -> None:
        nc_wait(_env['extgateway'], '5672')
        log_file = '{SNAP_COMMON}/log/rabbitmq/startup_log'.format(**_env)
        log_wait(log_file, 'completed')

    def _configure(self) -> None:
        """Configure RabbitMQ

        (actions may have already been run, in which case we fail silently).
        """
        # Add Erlang HOME to env.
        env = dict(**_env)
        env['HOME'] = '{SNAP_COMMON}/lib/rabbitmq'.format(**_env)
        # Configure RabbitMQ
        call('rabbitmqctl', 'add_user', 'openstack', 'rabbitmq', env=env)
        shell('rabbitmqctl set_permissions openstack ".*" ".*" ".*"', env=env)

    def yes(self, answer: str) -> None:
        log.info('Waiting for RabbitMQ to start ...')
        self._wait()
        log.info('RabbitMQ started!')
        log.info('Configuring RabbitMQ ...')
        self._configure()
        log.info('RabbitMQ Configured!')


class DatabaseSetup(Question):
    """Setup keystone permissions, then setup all databases."""

    def _wait(self) -> None:
        nc_wait(_env['extgateway'], '3306')
        log_wait('{SNAP_COMMON}/log/mysql/error.log'.format(**_env),
                 'mysqld: ready for connections.')

    def _create_dbs(self) -> None:
        for db in ('neutron', 'nova', 'nova_api', 'nova_cell0', 'cinder',
                   'glance', 'keystone'):
            sql("CREATE DATABASE IF NOT EXISTS {db};".format(db=db))
            sql(
                "GRANT ALL PRIVILEGES ON {db}.* TO {db}@{extgateway} \
                IDENTIFIED BY '{db}';".format(db=db, **_env))

    def _bootstrap(self) -> None:

        if call('openstack', 'user', 'show', 'admin'):
            return

        bootstrap_url = 'http://{extgateway}:5000/v3/'.format(**_env)

        check('snap-openstack', 'launch', 'keystone-manage', 'bootstrap',
              '--bootstrap-password', _env['ospassword'],
              '--bootstrap-admin-url', bootstrap_url,
              '--bootstrap-internal-url', bootstrap_url,
              '--bootstrap-public-url', bootstrap_url)

    def yes(self, answer: str) -> None:
        """Setup Databases.

        Create all the MySQL databases we require, then setup the
        fernet keys and create the service project.

        """
        log.info('Waiting for MySQL server to start ...')
        self._wait()
        log.info('Mysql server started! Creating databases ...')
        self._create_dbs()

        log.info('Configuring Keystone Fernet Keys ...')
        check('snap-openstack', 'launch', 'keystone-manage',
              'fernet_setup', '--keystone-user', 'root',
              '--keystone-group', 'root')
        check('snap-openstack', 'launch', 'keystone-manage', 'db_sync')

        restart('keystone-*')

        log.info('Bootstrapping Keystone ...')
        self._bootstrap()

        log.info('Creating service project ...')
        if not call('openstack', 'project', 'show', 'service'):
            check('openstack', 'project', 'create', '--domain',
                  'default', '--description', 'Service Project',
                  'service')

        log.info('Keystone configured!')


class NovaSetup(Question):
    """Create all relevant nova users and services."""

    def _flavors(self) -> None:
        """Create default flavors."""

        if not call('openstack', 'flavor', 'show', 'm1.tiny'):
            check('openstack', 'flavor', 'create', '--id', '1',
                  '--ram', '512', '--disk', '1', '--vcpus', '1', 'm1.tiny')
        if not call('openstack', 'flavor', 'show', 'm1.small'):
            check('openstack', 'flavor', 'create', '--id', '2',
                  '--ram', '2048', '--disk', '20', '--vcpus', '1', 'm1.small')
        if not call('openstack', 'flavor', 'show', 'm1.medium'):
            check('openstack', 'flavor', 'create', '--id', '3',
                  '--ram', '4096', '--disk', '20', '--vcpus', '2', 'm1.medium')
        if not call('openstack', 'flavor', 'show', 'm1.large'):
            check('openstack', 'flavor', 'create', '--id', '4',
                  '--ram', '8192', '--disk', '20', '--vcpus', '4', 'm1.large')
        if not call('openstack', 'flavor', 'show', 'm1.xlarge'):
            check('openstack', 'flavor', 'create', '--id', '5',
                  '--ram', '16384', '--disk', '20', '--vcpus', '8',
                  'm1.xlarge')

    def yes(self, answer: str) -> None:
        log.info('Configuring nova ...')

        if not call('openstack', 'user', 'show', 'nova'):
            check('openstack', 'user', 'create', '--domain',
                  'default', '--password', 'nova', 'nova')
            check('openstack', 'role', 'add', '--project',
                  'service', '--user', 'nova', 'admin')

        if not call('openstack', 'user', 'show', 'placement'):
            check('openstack', 'user', 'create', '--domain', 'default',
                  '--password', 'placement', 'placement')
            check('openstack', 'role', 'add', '--project', 'service',
                  '--user', 'placement', 'admin')

        if not call('openstack', 'service', 'show', 'compute'):
            check('openstack', 'service', 'create', '--name', 'nova',
                  '--description', '"Openstack Compute"', 'compute')
            for endpoint in ['public', 'internal', 'admin']:
                call('openstack', 'endpoint', 'create', '--region',
                     'microstack', 'compute', endpoint,
                     'http://{extgateway}:8774/v2.1'.format(**_env))

        if not call('openstack', 'service', 'show', 'placement'):
            check('openstack', 'service', 'create', '--name',
                  'placement', '--description', '"Placement API"',
                  'placement')

            for endpoint in ['public', 'internal', 'admin']:
                call('openstack', 'endpoint', 'create', '--region',
                     'microstack', 'placement', endpoint,
                     'http://{extgateway}:8778'.format(**_env))

        # Grant nova user access to cell0
        sql(
            "GRANT ALL PRIVILEGES ON nova_cell0.* TO 'nova'@'{extgateway}' \
            IDENTIFIED BY \'nova';".format(**_env))

        check('snap-openstack', 'launch', 'nova-manage', 'api_db', 'sync')

        if 'cell0' not in check_output('snap-openstack', 'launch',
                                       'nova-manage', 'cell_v2',
                                       'list_cells'):
            check('snap-openstack', 'launch', 'nova-manage',
                  'cell_v2', 'map_cell0')

        if 'cell1' not in check_output('snap-openstack', 'launch',
                                       'nova-manage', 'cell_v2', 'list_cells'):

            check('snap-openstack', 'launch', 'nova-manage', 'cell_v2',
                  'create_cell', '--name=cell1', '--verbose')

        check('snap-openstack', 'launch', 'nova-manage', 'db', 'sync')

        restart('nova-*')

        nc_wait(_env['extgateway'], '8774')

        sleep(5)  # TODO: log_wait

        log.info('Creating default flavors...')
        self._flavors()


class NeutronSetup(Question):
    """Create all relevant neutron services and users."""

    def yes(self, answer: str) -> None:
        log.info('Configuring Neutron')

        if not call('openstack', 'user', 'show', 'neutron'):
            check('openstack', 'user', 'create', '--domain', 'default',
                  '--password', 'neutron', 'neutron')
            check('openstack', 'role', 'add', '--project', 'service',
                  '--user', 'neutron', 'admin')

        if not call('openstack', 'service', 'show', 'network'):
            check('openstack', 'service', 'create', '--name', 'neutron',
                  '--description', '"OpenStack Network"', 'network')
            for endpoint in ['public', 'internal', 'admin']:
                call('openstack', 'endpoint', 'create', '--region',
                     'microstack', 'network', endpoint,
                     'http://{extgateway}:9696'.format(**_env))

        check('snap-openstack', 'launch', 'neutron-db-manage', 'upgrade',
              'head')

        restart('neutron-*')

        nc_wait(_env['extgateway'], '9696')

        sleep(5)  # TODO: log_wait

        if not call('openstack', 'network', 'show', 'test'):
            check('openstack', 'network', 'create', 'test')

        if not call('openstack', 'subnet', 'show', 'test-subnet'):
            check('openstack', 'subnet', 'create', '--network', 'test',
                  '--subnet-range', '192.168.222.0/24', 'test-subnet')

        if not call('openstack', 'network', 'show', 'external'):
            check('openstack', 'network', 'create', '--external',
                  '--provider-physical-network=physnet1',
                  '--provider-network-type=flat', 'external')
        if not call('openstack', 'subnet', 'show', 'external-subnet'):
            check('openstack', 'subnet', 'create', '--network', 'external',
                  '--subnet-range', _env['extcidr'], '--no-dhcp',
                  'external-subnet')

        if not call('openstack', 'router', 'show', 'test-router'):
            check('openstack', 'router', 'create', 'test-router')
            check('openstack', 'router', 'add', 'subnet', 'test-router',
                  'test-subnet')
            check('openstack', 'router', 'set', '--external-gateway',
                  'external', 'test-router')


class GlanceSetup(Question):
    """Setup glance, and download an initial Cirros image."""

    def _fetch_cirros(self) -> None:

        if call('openstack', 'image', 'show', 'cirros'):
            return

        env = dict(**_env)
        env['VER'] = '0.4.0'
        env['IMG'] = 'cirros-{VER}-x86_64-disk.img'.format(**env)

        log.info('Fetching cirros image ...')

        cirros_path = '{SNAP_COMMON}/images/{IMG}'.format(**env)

        if not path.exists(cirros_path):
            check('mkdir', '-p', '{SNAP_COMMON}/images'.format(**env))
            download(
                'http://download.cirros-cloud.net/{VER}/{IMG}'.format(**env),
                '{SNAP_COMMON}/images/{IMG}'.format(**env))

        check('openstack', 'image', 'create', '--file',
              '{SNAP_COMMON}/images/{IMG}'.format(**env),
              '--public', '--container-format=bare',
              '--disk-format=qcow2', 'cirros')

    def yes(self, answer: str) -> None:

        log.info('Configuring Glance ...')

        if not call('openstack', 'user', 'show', 'glance'):
            check('openstack', 'user', 'create', '--domain', 'default',
                  '--password', 'glance', 'glance')
            check('openstack', 'role', 'add', '--project', 'service',
                  '--user', 'glance', 'admin')

        if not call('openstack', 'service', 'show', 'image'):
            check('openstack', 'service', 'create', '--name', 'glance',
                  '--description', '"OpenStack Image"', 'image')
            for endpoint in ['internal', 'admin', 'public']:
                check('openstack', 'endpoint', 'create', '--region',
                      'microstack', 'image', endpoint,
                      'http://{extgateway}:9292'.format(**_env))

        check('snap-openstack', 'launch', 'glance-manage', 'db_sync')

        restart('glance*')

        nc_wait(_env['extgateway'], '9292')

        sleep(5)  # TODO: log_wait

        self._fetch_cirros()


class PostSetup(Question):
    """Sneak in any additional cleanup, then set the initialized state."""

    def yes(self, answer: str) -> None:

        log.info('restarting libvirt and virtlogd ...')
        # This fixes an issue w/ logging not getting set.
        # TODO: fix issue.
        restart('*virt*')

        check('snapctl', 'set', 'initialized=true')
        log.info('Complete. Marked microstack as initialized!')
