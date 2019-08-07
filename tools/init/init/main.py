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


def main() -> None:
    question_list = [
        questions.Setup(),
        questions.IpForwarding(),
        # The following are not yet implemented:
        # questions.VmSwappiness(),
        # questions.FileHandleLimits(),
        questions.RabbitMQ(),
        questions.DatabaseSetup(),
        questions.NovaSetup(),
        questions.NeutronSetup(),
        questions.GlanceSetup(),
        questions.PostSetup(),
    ]

    for question in question_list:
        try:
            question.ask()
        except questions.ConfigError as e:
            log.critical(e)
            sys.exit(1)


if __name__ == '__main__':
    main()
