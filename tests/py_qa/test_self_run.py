"""py-qa-ci's own run keeps every bundled defence on its own source.

CI runs `py-qa run` on this repository with no Ruff or mypy configuration of its own, so the
bundled Ruff selection, the bundled mypy configuration, the bundled Pylint plugin, the
suppression scan, the record and the documentation check all run on the code that implements
them. Nothing else would notice a change that quietly takes one of them off this source.
"""

import fnmatch
from pathlib import Path

import pytest

from py_qa.config import PATH_LANES, has_own_ruff_config, load_config
from py_qa.suppression import scope_files, within
from py_qa.tools import DEFAULTS, mypy_config_file

ROOT = Path(__file__).resolve().parents[2]
BUNDLED_LANES = ("pylint", "ruff", "mypy", "suppression", "record", "docs")
CI = ".github/workflows/ci.yml"


def self_run_gaps(root: Path) -> list[str]:
    """Return every way the project's own run leaves a bundled defence off its src/ code."""
    config = load_config(root)
    gaps = [f"the {lane} lane is switched off" for lane in BUNDLED_LANES if not config.tools[lane]]
    if has_own_ruff_config(root):
        gaps.append("a Ruff configuration of its own replaces the bundled one")
    if mypy_config_file(root).parent != DEFAULTS:
        gaps.append("a mypy configuration of its own replaces the bundled one")
    source = scope_files(root, (), ("src",))
    if not source:
        gaps.append("src/ holds no Python file")
    gaps.extend(
        f"scan_exclude {pattern} takes {name} out of the suppression scan and Pylint"
        for pattern in config.scan_exclude
        for name in source
        if fnmatch.fnmatchcase(name, pattern)
    )
    for lane in (*PATH_LANES, "suppression"):
        own = config.paths if lane == "suppression" else config.paths_for(lane)
        gaps.extend(
            f"the {lane} lane's paths leave out {name}"
            for name in source
            if not any(within(name, path) for path in own)
        )
    workflow = root / CI
    commands = workflow.read_text(encoding="utf-8").splitlines() if workflow.is_file() else []
    if not any(line.strip() == "run: uv run py-qa run" for line in commands):
        gaps.append(f"{CI} does not run every lane with `uv run py-qa run`")
    return gaps


def test_this_repository_runs_every_bundled_defence_on_its_own_source() -> None:
    assert self_run_gaps(ROOT) == []


@pytest.fixture
def copy(tmp_path: Path) -> Path:
    for name in ("pyproject.toml", CI, "src/py_qa/__init__.py"):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((ROOT / name).read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize(
    ("added", "gap"),
    [
        ("[tool.py-qa.tools]\npylint = false\n", "the pylint lane is switched off"),
        ("[tool.py-qa.tools]\nsuppression = false\n", "the suppression lane is switched off"),
        ("[tool.ruff]\nline-length = 100\n", "a Ruff configuration of its own"),
        ("[tool.mypy]\nstrict = true\n", "a mypy configuration of its own"),
        ("[tool.py-qa.lane_paths]\nmypy = ['tests']\n", "the mypy lane's paths leave out"),
    ],
)
def test_each_way_of_taking_a_defence_off_is_caught(copy: Path, added: str, gap: str) -> None:
    with (copy / "pyproject.toml").open("a", encoding="utf-8") as handle:
        handle.write("\n" + added)
    assert any(gap in found for found in self_run_gaps(copy))


def test_a_scan_exclude_over_src_is_caught(copy: Path) -> None:
    text = (copy / "pyproject.toml").read_text(encoding="utf-8")
    narrowed = text.replace(
        'paths = ["src", "tests"]', 'paths = ["src", "tests"]\nscan_exclude = ["src/*"]'
    )
    (copy / "pyproject.toml").write_text(narrowed, encoding="utf-8")
    assert any("scan_exclude src/*" in found for found in self_run_gaps(copy))


def test_a_ci_that_stops_running_py_qa_is_caught(copy: Path) -> None:
    (copy / CI).write_text("jobs: {}\n", encoding="utf-8")
    assert any(CI in found for found in self_run_gaps(copy))
