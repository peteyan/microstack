#!/usr/bin/env python3

import json

import requests

from cluster import shell
from cluster.shell import check_output


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

    credentials = resp['config']['credentials']
    control_creds = {f'config.credentials.{k}': v
                     for k, v in credentials.items()}
    shell.config_set(**control_creds)


if __name__ == '__main__':
    join()
