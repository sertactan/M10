from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path

from core.config.loader import load_yaml
from core.config.models import ApplicationConfig, ModelConfig


@dataclass(frozen=True)
class ReleaseReadiness:
    ready: bool
    blockers: tuple[str, ...]


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def check_release_readiness(root: Path) -> ReleaseReadiness:
    blockers: list[str] = []

    if not (root / "specs" / "s153_v14" / "manifest.json").exists():
        blockers.append("PHASE5_V14_CANONICAL_BUNDLE_MISSING")
    if not (root / "specs" / "s153_v141" / "canonical_completion_specification.md").exists():
        blockers.append("V141_CANONICAL_COMPLETION_SPEC_MISSING")

    required_modules = {
        "PHASE6_BACKTEST_ENGINE_MISSING": "core.backtest.engine",
        "PHASE7_SCANNER_MISSING": "core.scanner.engine",
        "PHASE8_EMPIRICAL_CALIBRATION_MISSING": "core.forecast.empirical_provider",
        "PHASE9_DESKTOP_UI_MISSING": "app.ui.launcher",
        "PHASE10_ANALYTICS_MISSING": "core.analytics.model_analytics",
        "PHASE11_OPTIMIZATION_MISSING": "core.optimization.parallel_scanner",
    }
    for blocker, module_name in required_modules.items():
        if not _module_available(module_name):
            blockers.append(blocker)

    v14_config = load_yaml(root / "config" / "s153_v14.yaml", ModelConfig)
    if not v14_config.enabled:
        blockers.append("PHASE5_V14_MODEL_DISABLED")

    v141_config = load_yaml(root / "config" / "s153_v141.yaml", ModelConfig)
    if not v141_config.enabled:
        blockers.append("V141_PRODUCTION_MODEL_DISABLED")

    app_config = load_yaml(root / "config" / "app.yaml", ApplicationConfig)
    if not app_config.strict_pit:
        blockers.append("STRICT_PIT_DISABLED")
    if app_config.allow_mock_data:
        blockers.append("MOCK_DATA_ENABLED")

    return ReleaseReadiness(
        ready=not blockers,
        blockers=tuple(blockers),
    )
