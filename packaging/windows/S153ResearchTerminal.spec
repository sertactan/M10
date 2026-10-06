# -*- mode: python ; coding: utf-8 -*-

import os

project_root = os.path.abspath(os.path.join(SPECPATH, "..", ".."))

a = Analysis(
    [os.path.join(project_root, "main.py")],
    pathex=[project_root],
    binaries=[],
    datas=[
        (os.path.join(project_root, "config"), "config"),
        (os.path.join(project_root, "specs", "s153_v14"), os.path.join("specs", "s153_v14")),
    ],
    hiddenimports=[
        "PySide6.QtCharts",
        "core.backtest.engine",
        "core.scanner.engine",
        "core.forecast.empirical_provider",
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
