from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Mapping

from core.models.s153_v12_contracts import S153V12Result
from core.models.s153_v14_contracts import S153V14Result


@dataclass(frozen=True)
class TerminalConsideration:
    effective_date: date
    value_per_share: float
    source_ref: str
    verified_within_252_session_horizon: bool


@dataclass(frozen=True)
class ForwardOutcome:
    security_id: str
    as_of_date_requested: date
    anchor_session: date | None
    anchor_lag_calendar_days: int | None
    entry_adjusted_close: float | None
    horizon_sessions_available: int
    fm252: float | None
    max_multiple_observed: float | None
    outcome_class: str | None
    time_to_2x_sessions: int | None = None
    time_to_3x_sessions: int | None = None
    time_to_5x_sessions: int | None = None
    time_to_7x_sessions: int | None = None
    time_to_10x_sessions: int | None = None
    outcome_status: str = "INCONCLUSIVE"
    diagnostics: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class HistoricalBacktestResult:
    security_id: str
    ticker: str
    as_of: datetime
    v12: S153V12Result
    v14: S153V14Result
    outcome: ForwardOutcome
    error_class_v12: str | None
    error_class_v14: str | None
