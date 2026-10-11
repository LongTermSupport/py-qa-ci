"""Run Pylint as the pylint lane does, with the project's own plugins importable.

`python -m pylint` drops the working directory from the import path, so a project's plugin in
the project (pylint_plugins) could not be loaded by the lane, though `py-qa rules` loads it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pylint

from py_qa.tools import project_import_paths


def main() -> None:
    """Run Pylint on the command line given, in the project the working directory is."""
    pylint.modify_sys_path()
    # Appended, so the project never shadows the standard library or Pylint itself; worker
    # processes start with this path, so they load the same plugins.
    sys.path.extend(project_import_paths(Path.cwd()))
    pylint.run_pylint()


if __name__ == "__main__":
    main()
