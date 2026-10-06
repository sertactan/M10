from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

from core.models.s16_contracts import S16Input


S16_REQUIRED_FEATURES = (
    "float_scarcity",
    "short_pressure",
    "float_turnover",
    "liquidity_elasticity",
    "ownership_lock",
    "catalyst",
    "volume_ignition",
    "momentum_acceleration",
    "social_velocity",
    "news_velocity",
    "regime_sympathy",
    "attention",
    "compression",
    "catalyst_proximity",
    "theme",
    "anomaly",
    "dilution_risk",
    "extension_risk",
    "data_risk",
    "liquidity_risk",
    "manipulation_risk",
)


class S16FeatureCoverageError(RuntimeError):
    pass


@dataclass(frozen=True)
class S16FeatureCoverage:
    present: int
    required: int
    coverage_pct: float
    missing: tuple[str, ...]
    score_ready: bool


def assess_feature_coverage(
    features: Mapping[str, float | None],
) -> S16FeatureCoverage:
    missing = tuple(
        key for key in S16_REQUIRED_FEATURES
        if features.get(key) is None
    )
    present = len(S16_REQUIRED_FEATURES) - len(missing)
    required = len(S16_REQUIRED_FEATURES)
    return S16FeatureCoverage(
        present=present,
        required=required,
        coverage_pct=100.0 * present / required,
        missing=missing,
        score_ready=not missing,
    )


def build_complete_s16_input(
    *,
    security_id: str,
    ticker: str,
    as_of: datetime,
    route: str | None,
    features: Mapping[str, float | None],
) -> S16Input:
    coverage = assess_feature_coverage(features)
    if not coverage.score_ready:
        raise S16FeatureCoverageError(
            "S16 PIT scoring is fail-closed; missing: " + ", ".join(coverage.missing)
        )
    payload = {key: float(features[key]) for key in S16_REQUIRED_FEATURES}
    return S16Input(
        security_id=security_id,
        ticker=ticker,
        as_of=as_of,
        route=route,
        **payload,
    )
