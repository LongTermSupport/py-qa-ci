"""Tests for the suppression scan: every route that silences a detector without the record.

The sources below spell each directive with "#@" for "# " and "#!" for a bare "#", so this file
holds no directive of its own for any tool or editor hook to act on.
"""

import subprocess
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from py_qa.record import RecordEntry
from py_qa.suppression import (
    Site,
    check_suppressions,
    comment_sites,
    config_sites,
    decorator_sites,
    named_files,
    project_files,
)

REASON = "The fixture deliberately holds the construction so the rule's red proof has a target."


def source(text: str) -> str:
    return text.replace("#@", "# ").replace("#!", "#")


def sites(text: str) -> list[tuple[int, str, tuple[str, ...]]]:
    return [(site.line, site.tool, site.codes) for site in comment_sites("a.py", source(text))]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("x = 1  #@noqa\n", [(1, "ruff", ())]),
        ("x = 1  #!NOQA:E501\n", [(1, "ruff", ("E501",))]),
        ("x = 1  #@noqa: E741, F841 because\n", [(1, "ruff", ("E741", "F841"))]),
        ("#@ruff: noqa\n", [(1, "ruff", ())]),
        ("#@flake8: noqa: F401\n", [(1, "ruff", ("F401",))]),
        ("#@ruff: ignore[ARG001, E501,]\n", [(1, "ruff", ("ARG001", "E501"))]),
        ("#@ruff: file-ignore[F401]\n", [(1, "ruff", ("F401",))]),
        ("#@ruff: disable[E501]\n#@ruff: enable[E501]\n", [(1, "ruff", ("E501",))]),
        ("import os  #@isort: skip\n", [(1, "ruff", ("I001",))]),
        ("#@isort: skip_file\n", [(1, "ruff", ("I001",))]),
        (
            "x = 1  #@pylint: disable=invalid-name, W0612\n",
            [(1, "pylint", ("invalid-name", "W0612"))],
        ),
        ("#@pylint:disable-next=too-many-locals\n", [(1, "pylint", ("too-many-locals",))]),
        ("#@pylint: disable=all\n", [(1, "pylint", ())]),
        ("#@pylint: skip-file\n", [(1, "pylint", ())]),
        (
            "x = 1  #@outbox is down here, so pylint: disable=proj-no-legacy-send\n",
            [(1, "pylint", ("proj-no-legacy-send",))],
        ),
        (
            "x = 1  #@pylint: disable=invalid-name; the name is the protocol's\n",
            [(1, "pylint", ("invalid-name",))],
        ),
        ("x = 1  #@see why, pylint: disable=all\n", [(1, "pylint", ())]),
        (
            "x = 1  #@type: ignore[misc]  #@pylint: disable=W0612\n",
            [(1, "mypy", ("misc",)), (1, "pylint", ("W0612",))],
        ),
        ("#@pylint: disable=W0612, enable=invalid-name\n", [(1, "pylint", ("W0612",))]),
        ("#@pylint: enable=invalid-name\n", []),
        ("#@pylint: disable=W0612, frobnicate=x\n", []),
        ("#@pylint: disable-next=C0103, enable=W0612=x\n", [(1, "pylint", ("C0103",))]),
        ("#@pylint : disable=invalid-name\n", []),
        ("x = 1  #@mentions pylint in prose\n", []),
        ("x = 1  #@type: ignore\n", [(1, "mypy", ())]),
        ("x = 1  #@type: ignore[arg-type, misc]\n", [(1, "mypy", ("arg-type", "misc"))]),
        ("#@mypy: ignore-errors\n", [(1, "mypy", ())]),
        (
            '#@mypy: disable-error-code="no-untyped-def, misc"\n',
            [(1, "mypy", ("no-untyped-def", "misc"))],
        ),
        ("#@mypy: allow-untyped-defs\n", [(1, "mypy", ("allow-untyped-defs",))]),
        ("#@mypy: warn-unreachable\n", []),
        ("x = 1  #@pyright: ignore\n", [(1, "pyright", ())]),
        (
            "x = 1  #@pyright: ignore[reportGeneralTypeIssues]\n",
            [(1, "pyright", ("reportGeneralTypeIssues",))],
        ),
        ("#@pyright: reportMissingImports=false\n", [(1, "pyright", ("reportMissingImports",))]),
        ("#@pyright: basic\n", [(1, "pyright", ("basic",))]),
        ("#@pyright: strict\n", []),
        ("x = 1  #@nosec\n", [(1, "bandit", ())]),
        ("x = 1  #@nosec B602, B607\n", [(1, "bandit", ("B602", "B607"))]),
        ("x = 1  #@nosemgrep\n", [(1, "semgrep", ())]),
        (
            "x = 1  #@nosemgrep: python.lang.rule-a\n",
            [(1, "semgrep", ("python.lang.rule-a",))],
        ),
        (
            "x = 1  #@type: ignore[misc]  #@noqa: E501\n",
            [(1, "mypy", ("misc",)), (1, "ruff", ("E501",))],
        ),
        ('x = "#@noqa"\n"""\n#@type: ignore\n"""\n', []),
        ("x = 1  #@this mentions noqa in prose\n", []),
    ],
)
def test_comment_forms(text: str, expected: list[tuple[int, str, tuple[str, ...]]]) -> None:
    assert sites(text) == expected


def test_unparseable_source_raises() -> None:
    with pytest.raises(SyntaxError):
        comment_sites("a.py", 'x = """  # no' + "qa\n")


def test_source_with_no_directive_word_is_not_tokenized() -> None:
    # Unparseable, but nothing in it could be a directive, so there is nothing to scan for.
    assert comment_sites("a.py", 'x = """\n') == []


NO_TYPE_CHECK = "no_type_check"


@pytest.mark.parametrize(
    ("text", "lines"),
    [
        ("import typing\n\n\n@typing.NTC\ndef d(text: str) -> int:\n    return text\n", [4]),
        ("from typing import NTC\n\n\n@NTC\ndef d(): ...\n", [4]),
        ("from typing_extensions import NTC\n\n\nclass C:\n    @NTC\n    def d(self): ...\n", [5]),
        ("import typing_extensions as te\n\n\n@te.NTC\nasync def d(): ...\n", [4]),
        ("from typing import NTC as unchecked\n\n\n@staticmethod\n@unchecked\ndef d(): ...\n", [5]),
        ("import typing as t\n\n\n@t.NTC\ndef d(): ...\n", [4]),
        # Not typing's decorator, so mypy checks the function.
        ("from mylib import NTC\n\n\n@NTC\ndef d(): ...\n", []),
        ("import mylib\n\n\n@mylib.NTC\ndef d(): ...\n", []),
        ('x = "@typing.NTC"\n', []),
    ],
)
def test_no_type_check_decorator_is_a_route(text: str, lines: list[int]) -> None:
    found = decorator_sites("a.py", text.replace("NTC", NO_TYPE_CHECK))
    assert [(site.line, site.rule_ids) for site in found] == [
        (line, (f"mypy::{NO_TYPE_CHECK}",)) for line in lines
    ]


def test_decorator_scan_reads_only_source_that_names_the_decorator() -> None:
    assert decorator_sites("a.py", "def broken(:\n") == []
    with pytest.raises(SyntaxError):
        decorator_sites("a.py", f"import typing\n@typing.{NO_TYPE_CHECK}\ndef broken(:\n")


def write(root: Path, name: str, text: str) -> None:
    (root / name).parent.mkdir(parents=True, exist_ok=True)
    (root / name).write_text(text, encoding="utf-8")


def test_pyproject_routes(tmp_path: Path) -> None:
    write(
        tmp_path,
        "pyproject.toml",
        """
[tool.ruff]
extend-exclude = ["gen"]
ignore = ["E741"]

[tool.ruff.lint]
select = ["E501", "S101"]
ignore = ["E501"]
extend-ignore = ["B008"]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101"]

[tool.mypy]
strict = true
disable_error_code = ["misc"]
exclude = ["build/"]

[[tool.mypy.overrides]]
module = "vendor.*"
ignore_errors = true
ignore_missing_imports = true
follow_imports = "skip"
""",
    )
    found = {(site.tool, site.codes) for site in config_sites(tmp_path)}
    assert found == {
        ("ruff", ("exclude",)),
        ("ruff", ("E741",)),
        ("ruff", ("E501",)),
        ("ruff", ("B008",)),
        ("ruff", ("S101",)),
        ("mypy", ("misc",)),
        ("mypy", ("exclude",)),
        ("mypy", ("ignore_errors",)),
        ("mypy", ("ignore_missing_imports",)),
        ("mypy", ("follow_imports",)),
    }
    assert all(site.path == "pyproject.toml" for site in config_sites(tmp_path))
    lines = {site.codes[0]: site.line for site in config_sites(tmp_path) if site.tool == "ruff"}
    assert lines["E501"] == 8
    assert lines["S101"] == 12
    assert lines["B008"] == 9


def test_ruff_toml_and_mypy_ini_routes(tmp_path: Path) -> None:
    write(tmp_path, "ruff.toml", '[lint]\nignore = ["E501"]\n')
    write(
        tmp_path,
        "mypy.ini",
        "[mypy]\ndisable_error_code = misc, attr-defined\n[mypy-x.*]\nignore_errors = True\n",
    )
    found = {(site.path, site.codes) for site in config_sites(tmp_path)}
    assert found == {
        ("ruff.toml", ("E501",)),
        ("mypy.ini", ("misc",)),
        ("mypy.ini", ("attr-defined",)),
        ("mypy.ini", ("ignore_errors",)),
    }


def test_settings_that_do_not_silence_are_not_routes(tmp_path: Path) -> None:
    write(
        tmp_path,
        "pyproject.toml",
        '[tool.ruff.lint]\nselect = ["E"]\n'
        '[tool.mypy]\nignore_errors = false\nfollow_imports = "normal"\n',
    )
    assert config_sites(tmp_path) == []


def entry(rule: str, path: str) -> RecordEntry:
    return RecordEntry(1, rule, path, REASON, "alice", date(2026, 1, 1), date(2026, 2, 1))


def test_recorded_site_passes_and_unrecorded_fails() -> None:
    found = [Site("a.py", 3, "ruff", ("E501", "F401"))]
    findings = check_suppressions(found, [entry("ruff::E501", "a.py")], full_scan=True)
    assert [f.render() for f in findings] == [
        "a.py:3: pyqaci.suppression.unrecorded ruff::F401 is suppressed here with no exception "
        "in the project record"
    ]


def test_blanket_fails_even_when_something_is_recorded() -> None:
    findings = check_suppressions([Site("a.py", 1, "mypy", ())], [], full_scan=True)
    assert [f.rule for f in findings] == ["pyqaci.suppression.blanket"]


def test_stale_entry_reported_only_on_a_full_scan() -> None:
    record = [entry("ruff::E501", "a.py")]
    stale = check_suppressions([], record, full_scan=True)
    assert [f.rule for f in stale] == ["pyqaci.record.stale"]
    assert check_suppressions([], record, full_scan=False) == []


def test_stale_entry_is_reported_where_it_is_written() -> None:
    record = [replace(entry("ruff::E501", "a.py"), line=7)]
    stale = check_suppressions([], record, full_scan=True, record_path="qa/record.toml")
    assert [f.render() for f in stale] == [
        "qa/record.toml:7: pyqaci.record.stale exception #1 (ruff::E501, a.py) covers no "
        "suppression; remove it"
    ]


def test_project_files_outside_git_skip_environments(tmp_path: Path) -> None:
    (tmp_path / ".venv" / "lib").mkdir(parents=True)
    (tmp_path / "pkg" / "gen").mkdir(parents=True)
    write(tmp_path, ".venv/lib/x.py", "")
    write(tmp_path, "pkg/a.py", "")
    write(tmp_path, "pkg/gen/b.py", "")
    assert project_files(tmp_path, ("pkg/gen/**",)) == ["pkg/a.py"]


def test_project_files_in_git_include_untracked_but_not_ignored(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    write(tmp_path, ".gitignore", "ignored.py\n")
    write(tmp_path, "ignored.py", "")
    write(tmp_path, "kept.py", "")
    write(tmp_path, "stub.pyi", "")
    assert project_files(tmp_path, ()) == ["kept.py", "stub.pyi"]


@pytest.mark.parametrize("in_git", [True, False])
def test_named_files_lists_every_kind_of_file_under_the_paths(tmp_path: Path, in_git: bool) -> None:
    if in_git:
        subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
        write(tmp_path, ".gitignore", "docs/ignored.md\n.venv/\n")
        write(tmp_path, "docs/ignored.md", "")
    for name in ("docs/guide.md", "docs/deep/page.md", "src/a.py", "docs/.venv/x.md"):
        write(tmp_path, name, "")
    expected = ["docs/deep/page.md", "docs/guide.md", "src/a.py"]
    assert named_files(tmp_path, ("docs", "src/a.py", "missing")) == expected


def test_mypy_strictness_turned_off_is_a_route(tmp_path: Path) -> None:
    write(
        tmp_path,
        "pyproject.toml",
        """
[tool.mypy]
strict = true
warn_unreachable = true
warn_return_any = false
disallow_untyped_defs = true

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false
disallow_any_generics = false
warn_unreachable = false
check_untyped_defs = true

[[tool.mypy.overrides]]
module = "legacy.*"
implicit_reexport = true
allow_untyped_globals = true
""",
    )
    found = {(site.line, site.codes, site.detail) for site in config_sites(tmp_path)}
    assert found == {
        (5, ("warn_return_any",), "every module"),
        (10, ("disallow_untyped_defs",), "tests.*"),
        (11, ("disallow_any_generics",), "tests.*"),
        (12, ("warn_unreachable",), "tests.*"),
        (17, ("implicit_reexport",), "legacy.*"),
        (18, ("allow_untyped_globals",), "legacy.*"),
    }


def test_mypy_flags_at_their_defaults_without_strict_are_not_routes(tmp_path: Path) -> None:
    write(
        tmp_path,
        "pyproject.toml",
        "[tool.mypy]\nwarn_return_any = false\nimplicit_reexport = true\n"
        '[[tool.mypy.overrides]]\nmodule = "a"\ndisallow_untyped_defs = false\n',
    )
    assert config_sites(tmp_path) == []


def test_mypy_ini_strictness_turned_off_in_a_section(tmp_path: Path) -> None:
    write(
        tmp_path,
        "mypy.ini",
        "[mypy]\nstrict = True\n\n[mypy-tests.*]\ndisallow_untyped_defs = False\n"
        "ignore_errors = True\n",
    )
    found = {(site.line, site.codes) for site in config_sites(tmp_path)}
    assert found == {(5, ("disallow_untyped_defs",)), (6, ("ignore_errors",))}


def test_a_key_repeated_in_an_override_is_reported_at_the_override(tmp_path: Path) -> None:
    write(
        tmp_path,
        "pyproject.toml",
        '[tool.mypy]\nignore_missing_imports = false\n\n[[tool.mypy.overrides]]\nmodule = "v"\n'
        "ignore_missing_imports = true\n",
    )
    assert [(site.line, site.codes) for site in config_sites(tmp_path)] == [
        (6, ("ignore_missing_imports",))
    ]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("def f():  #@pragma: no cover\n    pass\n", [(1, "coverage", ("no-cover",))]),
        ("if x:  #!PRAGMA NO COVER\n    pass\n", [(1, "coverage", ("no-cover",))]),
        ("while x:  #@pragma: no branch\n    pass\n", [(1, "coverage", ("no-branch",))]),
        ('x = "#@pragma: no cover"\n', []),
    ],
)
def test_coverage_exclusion_comments(
    text: str, expected: list[tuple[int, str, tuple[str, ...]]]
) -> None:
    assert sites(text) == expected


def test_coverage_configuration_routes(tmp_path: Path) -> None:
    write(
        tmp_path,
        "pyproject.toml",
        """
[tool.coverage.run]
branch = true
omit = ["tests/*"]

[tool.coverage.report]
fail_under = 95
exclude_lines = ["if TYPE_CHECKING:"]
exclude_also = ["raise NotImplementedError"]
partial_branches = ["while True:"]
""",
    )
    found = {(site.path, site.line, site.tool, site.codes) for site in config_sites(tmp_path)}
    assert found == {
        ("pyproject.toml", 4, "coverage", ("omit",)),
        ("pyproject.toml", 8, "coverage", ("exclude_lines",)),
        ("pyproject.toml", 9, "coverage", ("exclude_also",)),
        ("pyproject.toml", 10, "coverage", ("partial_branches",)),
    }


@pytest.mark.parametrize(
    ("name", "section"),
    [(".coveragerc", "report"), ("setup.cfg", "coverage:report"), ("tox.ini", "coverage:report")],
)
def test_coverage_ini_routes(tmp_path: Path, name: str, section: str) -> None:
    write(tmp_path, name, f"[{section}]\nexclude_lines =\n    if TYPE_CHECKING:\n")
    assert [(site.path, site.line, site.codes) for site in config_sites(tmp_path)] == [
        (name, 2, ("exclude_lines",))
    ]


def test_ruff_settings_are_reported_inside_ruffs_own_tables(tmp_path: Path) -> None:
    write(
        tmp_path,
        "pyproject.toml",
        """[tool.black]
extend-exclude = "gen"

[tool.deptry]
ignore = ["E501", "DEP002"]

[tool.ruff]
extend-exclude = ["gen"]

[tool.ruff.lint]
ignore = [
    "E501",
]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101"]
""",
    )
    found = {site.codes[0]: site.line for site in config_sites(tmp_path)}
    assert found == {"exclude": 8, "E501": 12, "S101": 16}


def test_ruff_toml_top_level_and_lint_tables(tmp_path: Path) -> None:
    write(tmp_path, "ruff.toml", 'exclude = ["gen"]\n\n[lint]\nignore = ["E501"]\n')
    found = {site.codes[0]: site.line for site in config_sites(tmp_path)}
    assert found == {"exclude": 1, "E501": 4}
