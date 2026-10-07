from __future__ import annotations

from datetime import date,datetime,timedelta,timezone

from core.backtest.contracts import ForwardOutcome
from core.backtest.wf5_replay import (
    _label_available_at,
    _replay_outcome_status,
)
from core.prices.models import (
    AdjustmentStatus,
    PriceQualityStatus,
    SourcePriceBar,
)


def _bar(day: date) -> SourcePriceBar:
    return SourcePriceBar(
        security_id="SEC_TEST",
        source="TEST",
        source_symbol="TEST",
        trade_date=day,
        open=10.0,
        high=10.0,
        low=10.0,
        raw_close=10.0,
        adjusted_close=10.0,
        volume=1000.0,
        vwap=None,
        retrieved_at=datetime(2026,1,1,tzinfo=timezone.utc),
        quality_status=PriceQualityStatus.CANONICAL,
        adjustment_status=AdjustmentStatus.ADJUSTED,
        raw_payload_hash=None,
    )


def _outcome(*, status: str, anchor: date) -> ForwardOutcome:
    return ForwardOutcome(
        security_id="SEC_TEST",
        as_of_date_requested=anchor,
        anchor_session=anchor,
        anchor_lag_calendar_days=0,
        entry_adjusted_close=10.0,
        horizon_sessions_available=252 if status=="READY" else 100,
        fm252=2.0 if status=="READY" else None,
        max_multiple_observed=2.0,
        outcome_class="MODERATE_WINNER" if status=="READY" else None,
        outcome_status=status,
        diagnostics={},
    )


def test_wf5_partial_is_censored_not_failure() -> None:
    assert _replay_outcome_status("PARTIAL") == "CENSORED"
    assert _replay_outcome_status("CENSORED") == "CENSORED"
    assert _replay_outcome_status("READY") == "READY"


def test_label_available_at_is_252nd_forward_session() -> None:
    anchor=date(2020,1,1)
    bars=[_bar(anchor)]
    bars.extend(_bar(anchor+timedelta(days=i)) for i in range(1,253))
    label_at=_label_available_at(bars,_outcome(status="READY",anchor=anchor))
    assert label_at is not None
    assert label_at.date() == anchor+timedelta(days=252)


def test_label_available_at_is_none_for_nonready_or_short_path() -> None:
    anchor=date(2020,1,1)
    short=[_bar(anchor)]
    short.extend(_bar(anchor+timedelta(days=i)) for i in range(1,100))
    assert _label_available_at(
        short,_outcome(status="READY",anchor=anchor)
    ) is None
    assert _label_available_at(
        short,_outcome(status="PARTIAL",anchor=anchor)
    ) is None
