from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.config.loader import load_yaml
from core.config.models import ModelConfig


@dataclass(frozen=True)
class ReleaseReadiness:
    ready: bool
    blockers: tuple[str, ...]


def check_release_readiness(root: Path) -> ReleaseReadiness:
    blockers: list[str] = []

    v14_manifest = root / "specs" / "s153_v14" / "manifest.json"
    phase6_manifest = root / "specs" / "phase6_backtest" / "manifest.json"

    if not v14_manifest.exists():
        blockers.append("PHASE5_V14_CANONICAL_BUNDLE_MISSING")
    if not phase6_manifest.exists():
        blockers.append("PHASE6_BACKTEST_CANONICAL_BUNDLE_MISSING")

    v14_config = load_yaml(root / "config" / "s153_v14.yaml", ModelConfig)
    if not v14_config.enabled:
        blockers.append("PHASE5_V14_MODEL_DISABLED")

    return ReleaseReadiness(
        ready=not blockers,
        blockers=tuple(blockers),
    )
