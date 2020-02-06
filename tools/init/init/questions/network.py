from init.config import Env, log
from init.questions.question import Question
from init.shell import check, check_output

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

    def no(self, answer: str) -> None:
        """This question doesn't actually work in a strictly confined snap, so
        we default to the no and a noop for now.

        """
        pass
