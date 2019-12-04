from init.config import Env, log
from init.questions.question import Question
from init.shell import check, check_output, restart
from os import path, remove

_env = Env().get_env()


class ExtGateway(Question):
    """Possibly override default ext gateway."""

    _type = 'string'
    _question = 'External Gateway'
    config_key = 'config.network.ext-gateway'

    def yes(self, answer):
        clustered = check_output('snapctl', 'get', 'config.clustered')
        if clustered.lower() != 'true':
            check('snapctl', 'set', 'config.network.control-ip={}'.format(
                answer))
            check('snapctl', 'set', 'config.network.compute-ip={}'.format(
                answer))
            _env['control_ip'] = _env['compute_ip'] = answer
        else:
            _env['control_ip'] = check_output('snapctl', 'get',
                                              'config.network.control-ip')
            _env['compute_ip'] = check_output('snapctl', 'get',
                                              'config.network.compute-ip')


class ExtCidr(Question):
    """Possibly override the cidr."""

    _type = 'string'
    _question = 'External Ip Range'
    config_key = 'config.network.ext-cidr'

    def yes(self, answer):
        _env['extcidr'] = answer


class IpForwarding(Question):
    """Possibly setup IP forwarding."""

    _type = 'boolean'  # Auto for now, to maintain old behavior.
    _question = 'Do you wish to setup ip forwarding? (recommended)'
    config_key = 'config.host.ip-forwarding'

    def yes(self, answer: str) -> None:
        """Use sysctl to setup ip forwarding."""
        log.info('Setting up ipv4 forwarding...')

        check('sysctl', 'net.ipv4.ip_forward=1')


class OvsDpdk(Question):
    """Possibly setup OVS DPDK."""

    _type = 'boolean'
    _question = 'Do you wish to setup OVS DPDK?'
    config_key = 'config.network.ovs-dpdk'
    interactive = True

    def yes(self, answer: bool):
        """Use ovs-vsctl to setup ovs-dpdk"""
        log.info('Setting up OVS DPDK...')
        check('snapctl', 'set', 'config.network.ovs-dpdk={}'.format(answer))

        check('ovs-wrapper', 'ovs-vsctl', '--no-wait', 'set', 'Open_vSwitch',
              '.', 'other_config:dpdk-init=true',
              'other_config:dpdk-socket-mem=1024,0',
              'other_config:pmd-cpu-mask=0x3')

        _path = """{SNAP_COMMON}/etc/neutron/neutron.conf.d/\
neutron-dpdk.conf""".format(**_env)

        with open(_path, 'w') as _file:
            _file.write("""\
[OVS]
datapath_type = netdev
vhostuser_socket_dir = {SNAP_COMMON}/run/openvswitch
""".format(**_env))

        # (re)configure alternatives based on the dpdk answer
        check('ovs-alternatives', '--install')

        restart('ovs*')
        restart('neutron*')

    def no(self, answer: bool):
        log.info('Setting up OVS...')
        check('snapctl', 'set', 'config.network.ovs-dpdk={}'.format(answer))

        # only remove config kept on default
        check('ovs-wrapper', 'ovs-vsctl', '--no-wait', 'remove',
              'Open_vSwitch', '.',
              'other_config', 'dpdk-init', 'true',
              'other_config', 'pmd-cpu-mask', '0x3',
              'dpdk-socket-mem', '1024,0')

        _path = """{SNAP_COMMON}/etc/neutron/neutron.conf.d/\
neutron-dpdk.conf""".format(**_env)

        if path.exists(_path):
            remove(_path)

        # (re)configure alternatives based on the dpdk answer
        check('ovs-alternatives', '--remove')
        check('ovs-alternatives', '--install')

        restart('ovs*')
        restart('neutron*')
