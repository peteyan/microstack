#!/usr/bin/env python3

import os
import socket

from init import shell
from init import credentials


def _get_default_config():
    snap_common = os.getenv('SNAP_COMMON')
    return {
        'config.clustered': False,
        'config.post-setup': True,
        'config.keystone.region-name': 'microstack',
        'config.credentials.key-pair': '/home/{USER}/snap/{SNAP_NAME}'
                                       '/common/.ssh/id_microstack',
        'config.network.node-fqdn': socket.getfqdn(),
        'config.network.dns-servers': '1.1.1.1',
        'config.network.dns-domain': 'microstack.example.',
        'config.network.ext-gateway': '10.20.20.1',
        'config.network.control-ip': '10.20.20.1',
        'config.network.compute-ip': '10.20.20.1',
        'config.network.ext-cidr': '10.20.20.1/24',
        'config.network.security-rules': True,
        'config.network.dashboard-allowed-hosts': '*',
        'config.network.ports.dashboard': 80,
        'config.network.ports.mysql': 3306,
        'config.network.ports.rabbit': 5672,
        'config.network.external-bridge-name': 'br-ex',
        'config.network.physnet-name': 'physnet1',
        'config.cinder.setup-loop-based-cinder-lvm-backend': False,
        'config.cinder.loop-device-file-size': '32G',
        'config.cinder.lvm-backend-volume-group': 'cinder-volumes',
        'config.host.ip-forwarding': False,
        'config.host.check-qemu': True,
        'config.services.control-plane': True,
        'config.services.hypervisor': True,
        'config.services.spice-console': True,
        'config.cluster.role': 'control',
        'config.cluster.password': 'null',
        'config.cleanup.delete-bridge': True,
        'config.cleanup.remove': True,
        'config.logging.custom-config': f'{snap_common}/etc/filebeat'
                                        '/filebeat-microstack.yaml',
        'config.logging.datatag': '',
        'config.logging.host': 'localhost:5044',
        'config.services.extra.enabled': False,
        'config.services.extra.filebeat': False,
        'config.alerting.custom-config': f'{snap_common}/etc/nrpe'
                                         '/nrpe-microstack.cfg',
        'config.services.extra.nrpe': False,
        'config.monitoring.ipmi': '',
        'config.services.extra.telegraf': False,
        'config.monitoring.custom-config': f'{snap_common}/etc/telegraf'
                                           '/telegraf-microstack.conf'
    }


def _set_default_config():
    shell.config_set(**_get_default_config())


def _setup_secrets():
    # If a user runs init multiple times we do not want to generate
    # new credentials to keep the init operation idempotent.
    existing_creds = shell.config_get('config.credentials')
    if isinstance(existing_creds, dict):
        existing_cred_keys = existing_creds.keys()
    else:
        existing_cred_keys = []
    shell.config_set(**{
        k: credentials.generate_password() for k in [
            'config.credentials.mysql-root-password',
            'config.credentials.rabbitmq-password',
            'config.credentials.keystone-password',
            'config.credentials.nova-password',
            'config.credentials.cinder-password',
            'config.credentials.neutron-password',
            'config.credentials.placement-password',
            'config.credentials.glance-password',
        ] if k not in existing_cred_keys
    })


if __name__ == '__main__':
    _set_default_config()
    _setup_secrets()
