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

from init.config import log
from init.shell import check

from init import questions


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--auto', '-a', action='store_true',
                        help='Run non interactively.')
    parser.add_argument('--cluster-password')
    parser.add_argument('--compute', action='store_true')
    parser.add_argument('--control', action='store_true')
    parser.add_argument('--debug', action='store_true')
    args = parser.parse_args()
    return args


def process_args(args):
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
        check('snapctl', 'set', 'config.cluster.password={}'.format(password))

    if args.debug:
        log.setLevel(logging.DEBUG)

    return auto


def main() -> None:
    args = parse_args()
    auto = process_args(args)

    question_list = [
        questions.Clustering(),
        questions.Dns(),
        questions.ExtGateway(),
        questions.ExtCidr(),
        questions.OsPassword(),  # TODO: turn this off if COMPUTE.
        questions.IpForwarding(),
        questions.ForceQemu(),
        # The following are not yet implemented:
        # questions.VmSwappiness(),
        # questions.FileHandleLimits(),
        questions.RabbitMq(),
        questions.DatabaseSetup(),
        questions.NovaHypervisor(),
        questions.NovaControlPlane(),
        questions.NeutronControlPlane(),
        questions.GlanceSetup(),
        questions.KeyPair(),
        questions.SecurityRules(),
        questions.PostSetup(),
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


if __name__ == '__main__':
    main()
