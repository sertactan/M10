from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping


@dataclass(frozen=True)
class S153V12Input:
    security_id: str
    ticker: str
    as_of: datetime
    discovery_factors: Mapping[int, float | None]
    control_factors: Mapping[str, float | None]
    features: Mapping[str, float | None]
    current_price: float | None = None
    current_market_cap: float | None = None


@dataclass(frozen=True)
class S153V12Result:
    security_id: str
    ticker: str
    as_of: datetime
    score: float | None
    status: str
    verdict: str | None
    primary_route: str | None
    secondary_route: str | None
    route_gate: bool
    confidence: float | None
    precision_confirmed: bool
    strong_watch: bool
    discovery: bool
    components: Mapping[str, float | None] = field(default_factory=dict)
    routes: Mapping[str, float | None] = field(default_factory=dict)
    flags: Mapping[str, bool] = field(default_factory=dict)
    missing_requirements: tuple[str, ...] = ()
