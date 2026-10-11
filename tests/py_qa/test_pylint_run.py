"""The Pylint launcher imports a project's own plugin from the project, as py-qa rules does."""

import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN = "def register(linter):\n    print('project plugin registered')\n"


@pytest.mark.parametrize("folder", [".", "src"])
def test_a_plugin_in_the_project_is_loaded(tmp_path: Path, folder: str) -> None:
    (tmp_path / folder).mkdir(exist_ok=True)
    (tmp_path / folder / "proj_launch_rules.py").write_text(PLUGIN, encoding="utf-8")
    (tmp_path / "clean.py").write_text("X = 1\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "py_qa.pylint_run", "--load-plugins=proj_launch_rules", "clean.py"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert "project plugin registered" in result.stdout
    assert "bad-plugin-value" not in result.stdout
