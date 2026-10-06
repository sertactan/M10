from __future__ import annotations

import logging
from pathlib import Path

import pytest

from app.bootstrap import AppContainer
from core.runtime.acceptance import (
    PHASE12_ACCEPTANCE_ITEMS,
    ProductionAcceptanceItem,
    require_phase12_complete,
)
from core.runtime.logging import configure_logging
from core.runtime.paths import writable_runtime_root
from core.runtime.readiness import check_release_readiness
from core.runtime.settings import RuntimeSettings
from core.runtime.update import UpdateManifestError, is_newer_version, parse_manifest


def test_runtime_settings_roundtrip_is_atomic(tmp_path):
    path = tmp_path / "settings.json"
    settings = RuntimeSettings(path)
    settings.save({"window_width": 1400, "last_ticker": "CRMD"})
    assert settings.load()["last_ticker"] == "CRMD"
    assert not path.with_suffix(".tmp").exists()


def test_update_manifest_validation_and_version_compare():
    manifest = parse_manifest(
        {
            "version": "1.2.3",
            "download_url": "https://example.invalid/setup.exe",
            "sha256": "a" * 64,
        }
    )
    assert manifest.version == "1.2.3"
    assert is_newer_version(current="1.2.2", candidate="1.2.3")
    assert not is_newer_version(current="1.2.3", candidate="1.2.3")
    with pytest.raises(UpdateManifestError):
        parse_manifest(
            {
                "version": "1.2.3",
                "download_url": "https://example.invalid/setup.exe",
                "sha256": "bad",
            }
        )


def test_runtime_root_override_is_writable(tmp_path, monkeypatch):
    monkeypatch.setenv("S153_RUNTIME_ROOT", str(tmp_path / "runtime"))
    root = writable_runtime_root(tmp_path / "project")
    assert root == (tmp_path / "runtime").resolve()
    assert root.exists()


def test_app_container_uses_runtime_override(tmp_path, monkeypatch):
    repo_root = Path(__file__).resolve().parents[1]
    runtime = tmp_path / "runtime"
    monkeypatch.setenv("S153_RUNTIME_ROOT", str(runtime))
    app = AppContainer(repo_root)
    try:
        assert str(app.sqlite.db_path).startswith(str(runtime.resolve()))
    finally:
        app.close()


def test_logging_uses_runtime_state_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    path = configure_logging(app_name="S153Test", level=logging.DEBUG)
    assert path.parent.exists()
    assert path.name == "app.log"
    assert str(path).startswith(str(tmp_path))


def test_windows_packaging_files_and_smoke_test_exist():
    root = Path(__file__).resolve().parents[1]
    spec = root / "packaging/windows/S153ResearchTerminal.spec"
    installer = root / "packaging/windows/S153ResearchTerminal.iss"
    workflow_path = root / ".github/workflows/windows-build.yml"
    assert spec.exists()
    assert installer.exists()
    workflow = workflow_path.read_text(encoding="utf-8")
    assert "pyinstaller" in workflow.lower()
    assert "innosetup" in workflow.lower()
    assert "--doctor" in workflow
    assert "S153ResearchTerminal-Setup.exe" in workflow


def test_release_readiness_passes_for_current_canonical_tree():
    root = Path(__file__).resolve().parents[1]
    result = check_release_readiness(root)
    assert result.ready is True
    assert result.blockers == ()


def test_phase12_acceptance_gate_requires_exact_scope():
    items = [
        ProductionAcceptanceItem(name=name, passed=True, evidence="tested")
        for name in PHASE12_ACCEPTANCE_ITEMS
    ]
    require_phase12_complete(items)
    assert len(PHASE12_ACCEPTANCE_ITEMS) == 7

    blocked = list(items)
    blocked[0] = ProductionAcceptanceItem(
        name="Windows executable build",
        passed=False,
        evidence="missing",
    )
    with pytest.raises(RuntimeError, match="Windows executable build"):
        require_phase12_complete(blocked)
