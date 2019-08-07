import sys
import os
import unittest

# TODO: drop in test runner and get rid of this line.
sys.path.append(os.getcwd())  # noqa

from init.question import (Question, InvalidQuestion, InvalidAnswer,
                           AnswerNotImplemented)


##############################################################################
#
# Test Fixtures
#
##############################################################################


class InvalidTypeQuestion(Question):
    _type = 'foo'


class IncompleteQuestion(Question):
    _type = 'auto'


class GoodAutoQuestion(Question):
    _type = 'auto'

    def yes(self, answer):
        return 'I am a good question!'


class GoodBinaryQuestion(Question):
    _type = 'binary'

    def yes(self, answer):
        return True

    def no(self, answer):
        return False


class GoodStringQuestion(Question):
    """Pass a string through to the output of Question.ask.

    # TODO right now, we have separate handlers for Truthy and Falsey
    answers, and this test class basically makes them do the same
    thing. Is this a good pattern?

    """
    _type = 'string'

    def yes(self, answer):
        return answer

    def no(self, answer):
        return answer


##############################################################################
#
# Tests Proper
#
##############################################################################


class TestQuestionClass(unittest.TestCase):
    """
    Test basic features of the Question class.

    """
    def test_invalid_type(self):

        with self.assertRaises(InvalidQuestion):
            InvalidTypeQuestion().ask()

    def test_valid_type(self):

        self.assertTrue(GoodBinaryQuestion())

    def test_not_implemented(self):

        with self.assertRaises(AnswerNotImplemented):
            IncompleteQuestion().ask()

    def test_auto_question(self):

        self.assertEqual(GoodAutoQuestion().ask(), 'I am a good question!')


class TestInput(unittest.TestCase):
    """
    Test input handling.

    Takes advantage of the fact that we can override the Question
    class's input handler.

    """
    def test_binary_question(self):

        q = GoodBinaryQuestion()

        for answer in ['yes', 'Yes', 'y']:
            q._input_func = lambda x: answer.encode('utf8')
            self.assertTrue(q.ask())

        for answer in ['No', 'n', 'no']:
            q._input_func = lambda x: answer.encode('utf8')
            self.assertFalse(q.ask())

        with self.assertRaises(InvalidAnswer):
            q._input_func = lambda x: 'foo'.encode('utf8')
            q.ask()

    def test_string_question(self):
        q = GoodStringQuestion()

        for answer in ['foo', 'bar', 'baz', '', 'yadayadayada']:
            q._input_func = lambda x: answer.encode('utf8')
            self.assertEqual(answer, q.ask())


if __name__ == '__main__':
    unittest.main()
