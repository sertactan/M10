from pathlib import Path

import pytest

from scripts.check_release_version import ReleaseVersionMismatch, require_aligned


def _write(root: Path, release: str, package: str, installer: str) -> None:
    (root / "config").mkdir(parents=True)
    (root / "packaging" / "windows").mkdir(parents=True)
    (root / "config" / "RELEASE_VERSION.txt").write_text(release + "\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        f'[project]\nname="x"\nversion="{package}"\n',
        encoding="utf-8",
    )
    (root / "packaging" / "windows" / "S153ResearchTerminal.iss").write_text(
        f"[Setup]\nAppVersion={installer}\n",
        encoding="utf-8",
    )


def test_release_versions_align(tmp_path):
    _write(tmp_path, "1.0.6", "1.0.6", "1.0.6")
    assert require_aligned(tmp_path)["release"] == "1.0.6"


def test_release_version_mismatch_fails_closed(tmp_path):
    _write(tmp_path, "1.0.6", "1.0.6", "0.0.1")
    with pytest.raises(ReleaseVersionMismatch, match="not aligned"):
        require_aligned(tmp_path)
