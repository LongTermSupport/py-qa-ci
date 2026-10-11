"""The Pylint checkers py-qa bundles; loaded in every project with --load-plugins."""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING

from pylint.lint import PyLinter

from py_qa.pylint_plugin.broad_suppress import BroadSuppressChecker
from py_qa.pylint_plugin.sensitive_repr import SensitiveReprChecker

if TYPE_CHECKING:
    from pylint.checkers import BaseChecker

CHECKERS = (SensitiveReprChecker, BroadSuppressChecker)
BUNDLED_MESSAGES = tuple(
    definition[1] for checker in CHECKERS for definition in checker.msgs.values()
)
_REGISTER = "register_checker"
_ONCE = "__pyqaci_once__"


def register(linter: PyLinter) -> None:
    """Register every bundled checker; Pylint calls this for each --load-plugins module."""
    _register_each_checker_once()
    for checker in CHECKERS:
        linter.register_checker(checker(linter))


def _register_each_checker_once() -> None:
    """Make registering a checker a linter already holds one of its class a no-op.

    Under --jobs, each worker receives the parent's linter with every checker registered and
    then calls every plugin's register again, so each plugin checker ran twice there and every
    finding was printed twice. The bundled plugin is loaded first, in the parent and in each
    worker, so this covers the project's plugins as well.
    """
    original = PyLinter.register_checker
    if getattr(original, _ONCE, False):
        return

    @functools.wraps(original)
    def once(linter: PyLinter, checker: BaseChecker) -> None:
        if any(type(known) is type(checker) for known in linter.get_checkers()):
            return
        original(linter, checker)

    setattr(once, _ONCE, True)
    setattr(PyLinter, _REGISTER, once)
