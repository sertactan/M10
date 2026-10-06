from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping


FORECAST_DISCLOSURE = (
    "FORWARD ESTIMATE — not a realized outcome; probabilities and scenarios "
    "must be supported by historical calibration evidence."
)


@dataclass(frozen=True)
class CalibratedForecast:
    calibration_id: str
    calibration_source: str
    calibration_cutoff: datetime
    sample_size: int
    bull_return_pct: float
    base_return_pct: float
    bear_return_pct: float
    probability_positive_return_pct: float
    probability_2x_plus_pct: float
    probability_5x_plus_pct: float
    probability_10x_plus_pct: float
    confidence_pct: float
    risk: str
    metadata: Mapping[str, object]


@dataclass(frozen=True)
class ForecastResult:
    security_id: str
    ticker: str
    as_of: datetime
    horizon_months: int
    v12_score: float | None
    v12_status: str
    v12_route: str | None
    v12_destination: str | None
    v14_score: float | None
    v14_status: str
    v14_route: str | None
    v14_destination: str | None
    bull_return_pct: float
    base_return_pct: float
    bear_return_pct: float
    probability_positive_return_pct: float
    probability_2x_plus_pct: float
    probability_5x_plus_pct: float
    probability_10x_plus_pct: float
    confidence_pct: float
    risk: str
    calibration_id: str
    calibration_source: str
    calibration_cutoff: datetime
    calibration_sample_size: int
    calibration_metadata: Mapping[str, object] = field(default_factory=dict)
    disclosure: str = FORECAST_DISCLOSURE
