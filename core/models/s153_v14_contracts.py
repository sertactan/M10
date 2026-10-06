from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping


@dataclass(frozen=True)
class S153V14Input:
    """Canonical PIT input contract for S15.3 V1.4.

    Phase 5 may only consume features materialized by the canonical data layer.
    The contract intentionally contains no V1.4 formulas, thresholds, probability
    mappings, destination rules, or missing-data substitutions.
    """

    security_id: str
    ticker: str
    as_of: datetime
    discovery_factors: Mapping[int, float | None]
    control_factors: Mapping[str, float | None]
    features: Mapping[str, float | None]
    current_price: float | None = None
    current_market_cap: float | None = None


@dataclass(frozen=True)
class S153V14Result:
    """Result surface reserved for the authoritative V1.4 specification.

    Every model-derived field remains optional until the canonical V1.4
    specifications are bound. No placeholder score or probability is permitted.
    """

    security_id: str
    ticker: str
    as_of: datetime
    score: float | None
    status: str
    primary_route: str | None = None
    secondary_route: str | None = None
    primary_magnitude: str | None = None
    extreme_magnitude: str | None = None
    acceleration_score: float | None = None
    large_winner_probability: float | None = None
    risk_adjusted_conviction: str | None = None
    confidence: float | None = None
    probability_buckets: Mapping[str, float | None] = field(default_factory=dict)
    components: Mapping[str, float | None] = field(default_factory=dict)
    flags: Mapping[str, bool] = field(default_factory=dict)
    missing_requirements: tuple[str, ...] = ()
