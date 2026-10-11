"""The bundled plugin registers every bundled checker with Pylint."""

from pylint.checkers import BaseChecker
from pylint.lint import PyLinter
from pylint.typing import MessageDefinitionTuple

from py_qa.pylint_plugin import BUNDLED_MESSAGES, register
from py_qa.pylint_plugin.sensitive_repr import SensitiveReprChecker


def test_register_adds_every_bundled_message() -> None:
    linter = PyLinter()
    register(linter)
    for symbol in BUNDLED_MESSAGES:
        assert linter.msgs_store.get_message_definitions(symbol)


def test_registering_again_adds_no_second_checker() -> None:
    # What each parallel worker does: the linter it receives already holds every checker.
    linter = PyLinter()
    register(linter)
    before = [type(checker) for checker in linter.get_checkers()]
    register(linter)
    linter.register_checker(SensitiveReprChecker(linter))
    assert [type(checker) for checker in linter.get_checkers()] == before


def test_a_checker_of_another_class_still_registers() -> None:
    linter = PyLinter()
    register(linter)
    count = len(linter.get_checkers())
    linter.register_checker(OtherChecker(linter))
    assert len(linter.get_checkers()) == count + 1


OTHER_MESSAGES: dict[str, MessageDefinitionTuple] = {
    "W9799": ("other", "pyqaci-test-other", "A message for the test only.")
}


class OtherChecker(BaseChecker):
    """A project checker that shares no class with the bundled ones."""

    name = "pyqaci-test-other"
    msgs = OTHER_MESSAGES
