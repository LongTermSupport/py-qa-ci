"""Every place a release names its own version agrees with pyproject.toml.

A project installs py-qa-ci by the README's install line, so a line still naming the previous
tag installs the previous release from the new one's README.
"""

import re
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[2]
INSTALL = re.compile(r"py-qa-ci @ git\+https://github\.com/LongTermSupport/py-qa-ci@v([^\"\s]+)")


def version_gaps(root: Path) -> list[str]:
    """Return every place that names a release other than the version pyproject.toml declares."""
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    version = pyproject["project"]["version"]
    readme = (root / "README.md").read_text(encoding="utf-8")
    pinned = INSTALL.findall(readme)
    gaps = [f"README.md installs v{tag}" for tag in pinned if tag != version]
    if not pinned:
        gaps.append("README.md has no install line pinning a tag")
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    latest = re.search(r"^## (\S+)", changelog, re.MULTILINE)
    if latest is None or latest.group(1) != version:
        gaps.append(f"CHANGELOG.md does not open with ## {version}")
    return gaps


def test_the_install_line_and_changelog_name_this_release() -> None:
    assert version_gaps(ROOT) == []


def test_an_install_line_naming_another_release_is_caught(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "1.2.0"\n', encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n## 1.1.0\n", encoding="utf-8")
    (tmp_path / "README.md").write_text(
        'uv add --dev "py-qa-ci @ git+https://github.com/LongTermSupport/py-qa-ci@v1.1.0"\n',
        encoding="utf-8",
    )
    assert version_gaps(tmp_path) == [
        "README.md installs v1.1.0",
        "CHANGELOG.md does not open with ## 1.2.0",
    ]
    (tmp_path / "README.md").write_text("uv add --dev py-qa-ci\n", encoding="utf-8")
    assert "README.md has no install line pinning a tag" in version_gaps(tmp_path)
