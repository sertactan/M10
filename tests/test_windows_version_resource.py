from pathlib import Path

import pytest

from scripts.windows_version_resource import render


def _root(tmp_path: Path, version: str) -> Path:
    (tmp_path / "config").mkdir()
    (tmp_path / "packaging" / "windows").mkdir(parents=True)
    (tmp_path / "config" / "RELEASE_VERSION.txt").write_text(version)
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nname="test"\nversion="{version}"\n'
    )
    (tmp_path / "packaging" / "windows" / "S153ResearchTerminal.iss").write_text(
        f"[Setup]\nAppVersion={version}\n"
    )
    return tmp_path


def test_version_resource_uses_canonical_release(tmp_path):
    resource = render(_root(tmp_path, "1.0.6"))
    assert "filevers=(1, 0, 6, 0)" in resource
    assert "ProductVersion', '1.0.6.0'" in resource


def test_invalid_pe_version_fails(tmp_path):
    with pytest.raises(ValueError, match="uint16"):
        render(_root(tmp_path, "1.0.70000"))
