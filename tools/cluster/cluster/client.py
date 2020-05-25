#!/usr/bin/env python3

import json

import requests

from cluster.shell import check, check_output, write_tunnel_config


def join():
    """Join an existing cluster as a compute node."""
    config = json.loads(check_output('snapctl', 'get', 'config'))

    password = config['cluster']['password']
    control_ip = config['network']['control-ip']
    my_ip = config['network']['compute-ip']

    if not password:
        raise Exception("No cluster password specified!")

    resp = requests.post(
        'http://{}:10002/join'.format(control_ip),
        json={'password': password, 'ip_address': my_ip})
    if resp.status_code != 200:
        # TODO better error and formatting.
        raise Exception('Failed to get info from control node: {}'.format(
            resp.json))
    resp = resp.json()

    # TODO: add better error handling to the below
    os_password = resp['config']['credentials']['os-password']

    # Write out tunnel config and restart neutron openvswitch agent.
    write_tunnel_config(my_ip)
    check('snapctl', 'restart', 'microstack.neutron-openvswitch-agent')

    # Set passwords and such
    check('snapctl', 'set', 'config.credentials.os-password={}'.format(
        os_password))


if __name__ == '__main__':
    join()
