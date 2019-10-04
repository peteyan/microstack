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
import sys

from init.config import log

from init import questions
from init.shell import check

# Figure out whether to prompt for user input, and which type of node
# we're running.
# TODO drop in argparse and formalize this.
COMPUTE = '--compute' in sys.argv
CONTROL = '--control' in sys.argv
AUTO = ('--auto' in sys.argv) or COMPUTE or CONTROL


def main() -> None:
    question_list = [
        questions.Dns(),
        questions.ExtGateway(),
        questions.ExtCidr(),
        questions.OsPassword(),  # TODO: turn this off if COMPUTE.
        questions.IpForwarding(),
        # The following are not yet implemented:
        # questions.VmSwappiness(),
        # questions.FileHandleLimits(),
        questions.RabbitMq(),
        questions.DatabaseSetup(),
        questions.NovaSetup(),
        questions.NeutronSetup(),
        questions.GlanceSetup(),
        questions.PostSetup(),
    ]

    # If we are setting up a "control" or "compute" node, override
    # some of the default yes/no questions.
    # TODO: move this into a nice little yaml parsing lib, and
    # allow people to pass in a config file from the command line.
    if CONTROL:
        check('snapctl', 'set', 'questions.nova-setup=false')

    if COMPUTE:
        check('snapctl', 'set', 'questions.rabbit-mq=false')
        check('snapctl', 'set', 'questions.database-setup=false')
        check('snapctl', 'set', 'questions.neutron-setup=false')
        check('snapctl', 'set', 'questions.glance-setup=false')

    for question in question_list:
        if AUTO:
            # If we are automatically answering questions, replace the
            # prompt for user input with a function that returns None,
            # causing the question to fall back to the already set
            # default
            question._input_func = lambda prompt: None

        try:
            question.ask()
        except questions.ConfigError as e:
            log.critical(e)
            sys.exit(1)


if __name__ == '__main__':
    main()
