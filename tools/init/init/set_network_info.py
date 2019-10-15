#!/usr/bin/env/python3
from init.shell import default_network, check

from init.config import log  # TODO name log.


def main():
    try:
        ip, gate, cidr = default_network()
    except Exception:
        # TODO: more specific exception handling.
        log.exception(
            'Could not determine default network info. '
            'Falling back on 10.20.20.1')
        return

    check('snapctl', 'set', 'config.network.ext-gateway={}'.format(gate))
    check('snapctl', 'set', 'config.network.ext-cidr={}'.format(cidr))
    check('snapctl', 'set', 'config.network.control-ip={}'.format(ip))
    check('snapctl', 'set', 'config.network.control-ip={}'.format(ip))


if __name__ == '__main__':
    main()
