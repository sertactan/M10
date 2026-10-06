from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping


@dataclass(frozen=True)
class S16Input:
    """Point-in-time normalized inputs for the 1-5 session explosive-move model.

    Signal fields are 0..100. Risk fields are 0..1. No future outcome may be
    present in this contract.
    """

    security_id: str
    ticker: str
    as_of: datetime
    route: str | None = None

    # FUEL / structural capacity
    market_cap_scarcity: float = 0.0
    float_scarcity: float = 0.0
    short_pressure: float = 0.0
    float_turnover: float = 0.0
    liquidity_elasticity: float = 0.0
    ownership_lock: float = 0.0

    # SPARK / ignition
    catalyst: float = 0.0
    volume_ignition: float = 0.0
    momentum_acceleration: float = 0.0
    social_velocity: float = 0.0
    news_velocity: float = 0.0
    regime_sympathy: float = 0.0

    # Pre-ignition / ARMED inputs
    attention: float = 0.0
    compression: float = 0.0
    catalyst_proximity: float = 0.0
    theme: float = 0.0
    anomaly: float = 0.0

    # Risk values are fractions in [0, 1].
    dilution_risk: float = 0.0
    extension_risk: float = 0.0
    data_risk: float = 0.0
    liquidity_risk: float = 0.0
    manipulation_risk: float = 0.0


@dataclass(frozen=True)
class S16Result:
    security_id: str
    ticker: str
    as_of: datetime
    version: str
    armed_score: float
    ignition_score: float
    fuel_score: float
    spark_score: float
    risk_penalty: float
    convergence_bonus: float
    status: str
    route: str | None = None
    explosive_score: float | None = None
    components: Mapping[str, float] = field(default_factory=dict)
    flags: Mapping[str, bool] = field(default_factory=dict)
