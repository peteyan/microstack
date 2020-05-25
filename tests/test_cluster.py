#!/usr/bin/env python
"""
cluster_test.py

This is a test to verify that we can setup a small, two node cluster.

The host running this test must have at least 16GB of RAM, four cpu
cores, a large amount of disk space, and the ability to run multipass
vms.

"""

import json
import os
import sys
import unittest

sys.path.append(os.getcwd())

from tests.framework import Framework, check, check_output, call  # noqa E402


os.environ['MULTIPASS'] = 'true'  # TODO better way to do this.


class TestCluster(Framework):

    def test_cluster(self):

        # After the setUp step, we should have a control node running
        # in a multipass vm. Let's look up its cluster password and ip
        # address.

        openstack = '/snap/bin/microstack.openstack'
        control_host = self.get_host()
        control_host.install()
        control_host.init(['--control'])

        control_prefix = control_host.prefix
        cluster_password = check_output(*control_prefix, 'sudo', 'snap',
                                        'get', 'microstack',
                                        'config.cluster.password')
        control_ip = check_output(*control_prefix, 'sudo', 'snap',
                                  'get', 'microstack',
                                  'config.network.control-ip')

        self.assertTrue(cluster_password)
        self.assertTrue(control_ip)

        compute_host = self.add_host()
        compute_host.install()

        compute_machine = compute_host.machine
        compute_prefix = compute_host.prefix

        # TODO add the following to args for init
        check(*compute_prefix, 'sudo', 'snap', 'set', 'microstack',
              'config.network.control-ip={}'.format(control_ip))

        check(*compute_prefix, 'sudo', 'microstack.init', '--compute',
              '--cluster-password', cluster_password, '--debug')

        # Verify that our services look setup properly on compute node.
        services = check_output(
            *compute_prefix, 'systemctl', 'status', 'snap.microstack.*',
            '--no-page')

        self.assertTrue('nova-compute' in services)
        self.assertFalse('keystone-' in services)

        check(*compute_prefix, '/snap/bin/microstack.launch', 'cirros',
              '--name', 'breakfast', '--retry',
              '--availability-zone', 'nova:{}'.format(compute_machine))

        # TODO: verify horizon dashboard on control node.

        # Verify endpoints
        compute_ip = check_output(*compute_prefix, 'sudo', 'snap',
                                  'get', 'microstack',
                                  'config.network.compute-ip')
        self.assertFalse(compute_ip == control_ip)

        # Ping the instance
        ip = None
        servers = check_output(*compute_prefix, openstack,
                               'server', 'list', '--format', 'json')
        servers = json.loads(servers)
        for server in servers:
            if server['Name'] == 'breakfast':
                ip = server['Networks'].split(",")[1].strip()
                break

        self.assertTrue(ip)

        pings = 1
        max_pings = 60  # ~1 minutes
        # Ping the machine from the control node (we don't have
        # networking wired up for the other nodes).
        while not call(*control_prefix, 'ping', '-c1', '-w1', ip):
            pings += 1
            if pings > max_pings:
                self.assertFalse(
                    True,
                    msg='Max pings reached for instance on {}!'.format(
                        compute_machine))

        self.passed = True

        # Compute machine cleanup
        check('sudo', 'multipass', 'delete', compute_machine)


if __name__ == '__main__':
    # Run our tests, ignoring deprecation warnings and warnings about
    # unclosed sockets. (TODO: setup a selenium server so that we can
    # move from PhantomJS, which is deprecated, to to Selenium headless.)
    unittest.main(warnings='ignore')
