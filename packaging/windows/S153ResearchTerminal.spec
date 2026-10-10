# -*- mode: python ; coding: utf-8 -*-

import os
import tempfile

project_root = os.path.abspath(os.path.join(SPECPATH, "..", ".."))

import sys
from pathlib import Path
sys.path.insert(0, project_root)
from scripts.phase26b_seed_gate import verify
from scripts.windows_version_resource import render as render_windows_version

seed_dir_text = os.environ.get("M10_RELEASE_SEED_DIR")
if not seed_dir_text:
    raise RuntimeError("M10_RELEASE_SEED_DIR is required; local or DB-derived seeds are forbidden")
seed_dir = Path(seed_dir_text).resolve()
notices = Path(project_root) / "THIRD_PARTY_DATA_LICENSES.md"
private_test = os.environ.get("M10_PRIVATE_TEST_PACKAGE") == "1"
approval_text = os.environ.get("M10_RELEASE_SEED_APPROVAL")
verify(seed_dir, notices, private_test=private_test,
       approval=Path(approval_text) if approval_text else None)
version_resource_dir = Path(tempfile.mkdtemp(prefix="m10-pe-version-"))
version_resource_file = version_resource_dir / "version.txt"
version_resource_file.write_text(render_windows_version(Path(project_root)), encoding="utf-8")

a = Analysis(
    [os.path.join(project_root, "main.py")],
    pathex=[project_root],
    binaries=[],
    datas=[
        (os.path.join(project_root, "config"), "config"),
        (os.path.join(project_root, "specs", "s153_v14"), os.path.join("specs", "s153_v14")),
        (os.path.join(project_root, "specs", "s153_v141"), os.path.join("specs", "s153_v141")),
        (
            os.path.join(project_root, "data", "database", "schema.sql"),
            os.path.join("data", "database"),
        ),
        (
            os.path.join(seed_dir, "sec_us_current.csv"),
            os.path.join("data", "seeds"),
        ),
        (
            os.path.join(seed_dir, "jp_tr_hk_current.csv"),
            os.path.join("data", "seeds"),
        ),
        (os.path.join(seed_dir, "manifest.json"), os.path.join("data", "seeds")),
        (
            os.path.join(project_root, "THIRD_PARTY_DATA_LICENSES.md"),
            ".",
        ),
    ],
    hiddenimports=[
        "PySide6.QtCharts",
        "core.backtest.engine",
        "core.models.s153_v141",
        "core.scanner.engine",
        "core.forecast.empirical_provider",
        "core.forecast.wf7_validated_provider",
        "core.backtest.wf8_hardening",
        "core.backtest.wf8_reproducibility",
        "core.backtest.wf8_activation",
        "app.ui.launcher",
        "core.analytics.model_analytics",
        "core.optimization.parallel_scanner",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="S153ResearchTerminal",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    version=str(version_resource_file),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="S153ResearchTerminal",
)
