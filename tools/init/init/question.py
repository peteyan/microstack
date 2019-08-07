"""question.py

Contains our Question class, which knows how to ask a question, then
run abitrary code.

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


from typing import Tuple


class InvalidQuestion(Exception):
    """Exception to raies in the case where a Question subclass has not
    been properly implemented.

    """


class InvalidAnswer(Exception):
    """Exception to raise in the case where the user has specified an
    invalid answer.

    """


class AnswerNotImplemented(Exception):
    """Exception to raise in the case where a 'yes' or 'no' routine has
    not been overriden in the subclass, as required.

    """


class Question():
    """
    Ask the user a question, and then run code as appropriate.

    Contains a support for always defaulting to yes.

    TODO: Add support for finding answers in a config.yaml.

    """
    _valid_types = [
        'binary',  # Yes or No, and variants thereof
        'string',  # Accept (and sanitize) any string
        'auto'  # Don't actually ask a question -- just execute self.yes(True)
    ]

    _question = '(required)'
    _type = 'auto'  # can be binary, string or auto
    _invalid_prompt = 'Please answer Yes or No.'
    _retries = 3
    _input_func = input

    def __init__(self):

        if self._type not in ['binary', 'string', 'auto']:
            raise InvalidQuestion(
                'Invalid type {} specified'.format(self._type))

    def _validate(self, answer: bytes) -> Tuple[str, bool]:
        """Validate an answer.

        :param anwser: raw input from the user.

        Returns the answer, and whether or not the answer was valid.

        """
        if self._type == 'auto':
            return True, True

        answer = answer.decode('utf8')

        if self._type == 'string':
            # TODO Santize this!
            return answer, True

        # self._type is binary
        if answer.lower() in ['y', 'yes']:
            return True, True

        if answer.lower() in ['n', 'no']:
            return False, True

        return answer, False

    def yes(self, answer: str) -> None:
        """Routine to run if the user answers 'yes' or with a value."""
        raise AnswerNotImplemented('You must override this method.')

    def no(self, answer: str) -> None:
        """Routine to run if the user answers 'no'"""
        raise AnswerNotImplemented('You must override this method.')

    def ask(self) -> None:
        """
        Ask the user a question.

        Run self.yes or self.no as appropriate. Raise an error if the
        user cannot specify a valid answer after self._retries tries.

        """
        prompt = self._question

        for i in range(0, self._retries):
            awr, valid = self._validate(
                self._type == 'auto' or self._input_func(prompt))
            if valid:
                if awr:
                    return self.yes(awr)
                return self.no(awr)
            prompt = '{} is not valid. {}'.format(awr, self._invalid_prompt)

        raise InvalidAnswer('Too many invalid answers.')
