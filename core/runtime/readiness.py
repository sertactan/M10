from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.config.loader import load_yaml
from core.config.models import ApplicationConfig, ModelConfig


@dataclass(frozen=True)
class ReleaseReadiness:
    ready: bool
    blockers: tuple[str, ...]


def check_release_readiness(root: Path) -> ReleaseReadiness:
    blockers: list[str] = []

    required_files = {
        "PHASE5_V14_CANONICAL_BUNDLE_MISSING": root / "specs" / "s153_v14" / "manifest.json",
        "PHASE8_EMPIRICAL_CALIBRATION_MISSING": root / "core" / "forecast" / "empirical_provider.py",
        "PHASE9_DESKTOP_UI_MISSING": root / "app" / "ui" / "launcher.py",
        "PHASE12_WINDOWS_SPEC_MISSING": root / "packaging" / "windows" / "S153ResearchTerminal.spec",
        "PHASE12_INSTALLER_SPEC_MISSING": root / "packaging" / "windows" / "S153ResearchTerminal.iss",
    }
    for blocker, path in required_files.items():
        if not path.exists():
            blockers.append(blocker)

    v14_config = load_yaml(root / "config" / "s153_v14.yaml", ModelConfig)
    if not v14_config.enabled:
        blockers.append("PHASE5_V14_MODEL_DISABLED")

    app_config = load_yaml(root / "config" / "app.yaml", ApplicationConfig)
    if not app_config.strict_pit:
        blockers.append("STRICT_PIT_DISABLED")
    if app_config.allow_mock_data:
        blockers.append("MOCK_DATA_ENABLED")

    return ReleaseReadiness(
        ready=not blockers,
        blockers=tuple(blockers),
    )
