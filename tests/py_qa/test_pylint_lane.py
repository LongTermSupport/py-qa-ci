"""The Pylint lane reaches every file in the sweep scope, whatever the package layout.

Given a directory, Pylint walks only importable packages, so a file in a directory without an
__init__.py below a package was never analysed and the lane reported clean. These tests run the
real lane on that layout.
"""

import io
from datetime import UTC, datetime
from pathlib import Path

import pytest

from py_qa.config import load_config
from py_qa.pipeline import run_pipeline

BROAD = "import contextlib\n\nwith contextlib.suppress(Exception):\n    pass\n"


def layout(root: Path) -> None:
    (root / "pyproject.toml").write_text("", encoding="utf-8")
    nested = root / "tests" / "unit" / "daemon"
    nested.mkdir(parents=True)
    (root / "tests" / "__init__.py").write_text("", encoding="utf-8")
    (root / "tests" / "unit" / "__init__.py").write_text("", encoding="utf-8")
    (nested / "test_nested.py").write_text(BROAD, encoding="utf-8")
    (root / "src").mkdir()
    (root / "src" / "clean.py").write_text("X = 1\n", encoding="utf-8")


def pylint_lane(root: Path, paths: tuple[str, ...] | None) -> int:
    return run_pipeline(
        load_config(root),
        requested=("pylint",),
        paths=paths,
        no_fix=True,
        fail_fast=False,
        out=io.StringIO(),
        today=datetime.now(tz=UTC).date(),
    )


@pytest.mark.parametrize("paths", [None, ("tests",), ("tests/unit",)])
def test_file_below_a_non_package_directory_is_analysed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
    paths: tuple[str, ...] | None,
) -> None:
    layout(tmp_path)
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    assert pylint_lane(tmp_path, paths) == 1
    assert "tests/unit/daemon/test_nested.py:3:5: W9702" in capfd.readouterr().out


def test_clean_scope_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    layout(tmp_path)
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    assert pylint_lane(tmp_path, ("src",)) == 0


PROJECT_PLUGIN = '''"""A project checker: flags a call to shout."""

from pylint.checkers import BaseChecker


class NoShoutChecker(BaseChecker):
    name = "proj-no-shout"
    msgs = {"W9801": ("shout called", "proj-no-shout", "Do not call shout.")}

    def visit_call(self, node):
        if getattr(node.func, "name", None) == "shout":
            self.add_message("proj-no-shout", node=node)


def register(linter):
    linter.register_checker(NoShoutChecker(linter))
'''


def test_each_finding_is_reported_once_under_parallel_workers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    # Pylint re-registers every plugin in each worker over the checkers the parent already
    # registered, so a plugin's checker ran twice there and printed each finding twice.
    layout(tmp_path)
    # A module name no other test imports: py-qa lists the messages from the module in-process.
    (tmp_path / "pyproject.toml").write_text(
        '[tool.py-qa]\npylint_plugins = ["proj_shout_rules"]\n', encoding="utf-8"
    )
    (tmp_path / "proj_shout_rules.py").write_text(PROJECT_PLUGIN, encoding="utf-8")
    (tmp_path / "src" / "shouts.py").write_text("shout('1')\n", encoding="utf-8")
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    assert pylint_lane(tmp_path, ("src", "tests")) == 1
    out = capfd.readouterr().out
    assert out.count("tests/unit/daemon/test_nested.py:3:5: W9702") == 1
    assert out.count("src/shouts.py:1:0: W9801") == 1
