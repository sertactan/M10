from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelView:
    model_name: str
    status: str
    score: float | None = None
    route: str | None = None
    destination: str | None = None
    confidence: float | None = None
    risk: str | None = None


@dataclass(frozen=True)
class ComparisonView:
    v12: ModelView
    v14: ModelView
    consensus: str | None = None
    winner: str | None = None
    combined_conviction: str | None = None


@dataclass(frozen=True)
class StockHeaderView:
    ticker: str
    name: str
    exchange: str
    status: str
    price: float | None = None
    change_pct: float | None = None
    price_date: str | None = None
    price_source: str | None = None


@dataclass(frozen=True)
class BacktestView:
    status: str
    entry_price: float | None = None
    fm252: float | None = None
    max_multiple_observed: float | None = None
    outcome_class: str | None = None
    anchor_session: str | None = None
    horizon_sessions_available: int | None = None
    time_to_2x_sessions: int | None = None
    time_to_5x_sessions: int | None = None
    time_to_10x_sessions: int | None = None


@dataclass(frozen=True)
class ForecastView:
    status: str
    bull_return_pct: float | None = None
    base_return_pct: float | None = None
    bear_return_pct: float | None = None
    probability_positive_return_pct: float | None = None
    probability_2x_plus_pct: float | None = None
    probability_5x_plus_pct: float | None = None
    probability_10x_plus_pct: float | None = None
    confidence_pct: float | None = None
    risk: str | None = None
    calibration_id: str | None = None
    analysis_id: str | None = None
