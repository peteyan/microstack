"""Microstack Init

Initialize the databases and configuration files of a microstack
install.

We structure our init in the form of 'Question' classes, each of which
has an 'ask' routine, run in the order laid out in the
question_classes in the main function in this file.

.ask will either ask the user a question, and run the appropriate
routine in the Question class, or simply automatically run a routine
without input from the user (in the case of 'required' questions).

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

import argparse
import logging
import secrets
import string
import sys
import socket

from functools import wraps

from init.config import log
from init.shell import default_network, check, check_output

from init import questions


def requires_sudo(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if int(check_output('id', '-u')):
            log.error("This script must be run with root privileges. "
                      "Please re-run with sudo.")
            sys.exit(1)

        return func(*args, **kwargs)
    return wrapper


def check_file_size_positive(value):
    ival = int(value)
    if ival < 1:
        raise argparse.ArgumentTypeError(
                f'The file size for a loop device'
                f' must be larger than 1GB, current: {value}')
    return ival


def parse_init_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--auto', '-a', action='store_true',
                        help='Run non interactively.')
    parser.add_argument('--cluster-password')
    parser.add_argument('--compute', action='store_true')
    parser.add_argument('--control', action='store_true')
    parser.add_argument('--debug', action='store_true')
    parser.add_argument(
            '--setup-loop-based-cinder-lvm-backend',
            action='store_true',
            help='(experimental) set up a loop device-backed'
                 ' LVM backend for Cinder.'
    )
    parser.add_argument(
            '--loop-device-file-size',
            type=check_file_size_positive, default=32,
            help=('File size in GB (10^9) of a file to be exposed as a loop'
                  ' device for the Cinder LVM backend.')
    )
    args = parser.parse_args()
    return args


def process_init_args(args):
    """Look through our args object and set the proper default config
    values in our snap config, based on those args.

    """
    auto = args.auto or args.control or args.compute

    if args.compute or args.control:
        check('snapctl', 'set', 'config.clustered=true')

    if args.compute:
        check('snapctl', 'set', 'config.cluster.role=compute')

    if args.control:
        # If both compute and control are passed for some reason, we
        # wind up with the role of 'control', which is best, as a
        # control node also serves as a compute node in our hyper
        # converged architecture.
        check('snapctl', 'set', 'config.cluster.role=control')

    if args.cluster_password:
        check('snapctl', 'set', 'config.cluster.password={}'.format(
            args.cluster_password))

    if auto and not args.cluster_password:
        alphabet = string.ascii_letters + string.digits
        password = ''.join(secrets.choice(alphabet) for i in range(10))
        check('snapctl', 'set', 'config.cluster.password={}'.format(
            password))

    if args.debug:
        log.setLevel(logging.DEBUG)

    check('snapctl', 'set',
          f'config.cinder.setup-loop-based-cinder-lvm-backend='
          f'{str(args.setup_loop_based_cinder_lvm_backend).lower()}')
    check('snapctl', 'set',
          f'config.cinder.loop-device-file-size={args.loop_device_file_size}G')

    return auto


@requires_sudo
def init() -> None:
    args = parse_init_args()
    auto = process_init_args(args)

    question_list = [
        questions.Clustering(),
        questions.DnsServers(),
        questions.DnsDomain(),
        questions.NetworkSettings(),
        questions.OsPassword(),  # TODO: turn this off if COMPUTE.
        questions.ForceQemu(),
        # The following are not yet implemented:
        # questions.VmSwappiness(),
        # questions.FileHandleLimits(),
        questions.DashboardAccess(),
        questions.RabbitMq(),
        questions.DatabaseSetup(),
        questions.PlacementSetup(),
        questions.NovaControlPlane(),
        questions.NovaHypervisor(),
        questions.NovaSpiceConsoleSetup(),
        questions.NeutronControlPlane(),
        questions.GlanceSetup(),
        questions.SecurityRules(),
        questions.CinderSetup(),
        questions.CinderVolumeLVMSetup(),
        questions.PostSetup(),
        questions.ExtraServicesQuestion(),
    ]

    for question in question_list:
        if auto:
            # Force all questions to be non-interactive if we passed --auto.
            question.interactive = False

        try:
            question.ask()
        except questions.ConfigError as e:
            log.critical(e)
            sys.exit(1)


def set_network_info() -> None:
    """Find and use the  default network on a machine.

    Helper to find the default network on a machine, and configure
    MicroStack to use it in its default settings.

    """
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
    check('snapctl', 'set',
          'config.network.node-fqdn={}'.format(socket.getfqdn()))


@requires_sudo
def remove() -> None:
    """Helper to cleanly uninstall MicroStack."""

    # Strip '--auto' out of the args passed to this command, as we
    # need to check it, but also pass the other args off to the
    # snapd's uninstall command. TODO: make this less hacky.
    auto = False
    if '--auto' in questions.uninstall.ARGS:
        auto = True
    questions.uninstall.ARGS = [
        arg for arg in questions.uninstall.ARGS if 'auto' not in arg]

    question_list = [
        questions.uninstall.DeleteBridge(),
        questions.uninstall.RemoveMicrostack(),
    ]

    for question in question_list:
        if auto:
            question.interactive = False
        question.ask()
