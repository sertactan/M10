from __future__ import annotations

from datetime import date
from typing import Iterable

from core.backtest.contracts import ForwardOutcome, TerminalConsideration
from core.prices.models import SourcePriceBar
from core.prices.policy import PriceSelectionPolicy


def _classify_fm252(value: float) -> str:
    if value >= 10.0:
        return "TRUE_10X"
    if value >= 7.0:
        return "NEAR_MISS_10X"
    if value >= 5.0:
        return "MAJOR_WINNER"
    if value >= 3.0:
        return "STRONG_WINNER"
    if value >= 2.0:
        return "MODERATE_WINNER"
    return "FAILURE"


def _time_to_multiple(
    closes: list[float],
    entry: float,
    multiple: float,
) -> int | None:
    target = entry * multiple
    for session_index, close in enumerate(closes, start=1):
        if close >= target:
            return session_index
    return None


class CanonicalForwardOutcomeEngine:
    """Compute source-defined 252-session labels from one canonical adjusted series.

    The model/feature process must run before this outcome is joined to scores.
    """

    def compute(
        self,
        *,
        security_id: str,
        as_of_date_requested: date,
        bars: Iterable[SourcePriceBar],
        terminal_consideration: TerminalConsideration | None = None,
        terminal_value_unknown: bool = False,
    ) -> ForwardOutcome:
        ordered = sorted(list(bars), key=lambda b: b.trade_date)
        if not ordered:
            return ForwardOutcome(
                security_id=security_id,
                as_of_date_requested=as_of_date_requested,
                anchor_session=None,
                anchor_lag_calendar_days=None,
                entry_adjusted_close=None,
                horizon_sessions_available=0,
                fm252=None,
                max_multiple_observed=None,
                outcome_class=None,
                outcome_status="INVALID_PRICE",
                diagnostics={"reason": "no canonical price bars"},
            )

        PriceSelectionPolicy.assert_single_source(ordered)
        identities = {b.security_id for b in ordered}
        if identities != {security_id}:
            return ForwardOutcome(
                security_id=security_id,
                as_of_date_requested=as_of_date_requested,
                anchor_session=None,
                anchor_lag_calendar_days=None,
                entry_adjusted_close=None,
                horizon_sessions_available=0,
                fm252=None,
                max_multiple_observed=None,
                outcome_class=None,
                outcome_status="INVALID_IDENTITY",
                diagnostics={"bar_security_ids": sorted(identities)},
            )

        completed = [b for b in ordered if b.trade_date <= as_of_date_requested]
        if not completed:
            return ForwardOutcome(
                security_id=security_id,
                as_of_date_requested=as_of_date_requested,
                anchor_session=None,
                anchor_lag_calendar_days=None,
                entry_adjusted_close=None,
                horizon_sessions_available=0,
                fm252=None,
                max_multiple_observed=None,
                outcome_class=None,
                outcome_status="INVALID_PRICE",
                diagnostics={"reason": "no completed trading session on/before as_of_date"},
            )

        anchor = completed[-1]
        entry = float(anchor.adjusted_close)
        if entry <= 0:
            return ForwardOutcome(
                security_id=security_id,
                as_of_date_requested=as_of_date_requested,
                anchor_session=anchor.trade_date,
                anchor_lag_calendar_days=(as_of_date_requested - anchor.trade_date).days,
                entry_adjusted_close=entry,
                horizon_sessions_available=0,
                fm252=None,
                max_multiple_observed=None,
                outcome_class=None,
                outcome_status="INVALID_PRICE",
                diagnostics={"reason": "non-positive anchor adjusted close"},
            )

        forward = [b for b in ordered if b.trade_date > anchor.trade_date][:252]
        bar_closes = [float(b.adjusted_close) for b in forward if float(b.adjusted_close) > 0]
        outcome_values = list(bar_closes)

        terminal_in_horizon = False
        if terminal_consideration is not None:
            # Exact trading-session placement of a non-session terminal date belongs
            # to the authoritative Trading Calendar / Corporate Action specs.
            # We therefore use terminal consideration for terminal value / FM252,
            # but do not fabricate a time_to_kX session index from it.
            horizon_last = forward[-1].trade_date if forward else terminal_consideration.effective_date
            if anchor.trade_date < terminal_consideration.effective_date <= horizon_last:
                outcome_values.append(float(terminal_consideration.value_per_share))
                terminal_in_horizon = True

        max_multiple = max(outcome_values) / entry if outcome_values else None

        if terminal_value_unknown:
            status = "CENSORED"
            fm252 = None
            outcome_class = None
        elif terminal_in_horizon:
            # The canonical historical spec says reliable terminal consideration
            # is added to the outcome series; unknown terminal value is censored.
            # A known terminal therefore closes the observable path without
            # inventing post-delisting prices.
            status = "READY"
            fm252 = max_multiple
            outcome_class = _classify_fm252(fm252) if fm252 is not None else None
        elif len(forward) < 252:
            status = "PARTIAL"
            fm252 = None
            outcome_class = None
        else:
            status = "READY"
            fm252 = max_multiple
            outcome_class = _classify_fm252(fm252) if fm252 is not None else None

        return ForwardOutcome(
            security_id=security_id,
            as_of_date_requested=as_of_date_requested,
            anchor_session=anchor.trade_date,
            anchor_lag_calendar_days=(as_of_date_requested - anchor.trade_date).days,
            entry_adjusted_close=entry,
            horizon_sessions_available=len(forward),
            fm252=fm252,
            max_multiple_observed=max_multiple,
            outcome_class=outcome_class,
            time_to_2x_sessions=_time_to_multiple(bar_closes, entry, 2.0),
            time_to_3x_sessions=_time_to_multiple(bar_closes, entry, 3.0),
            time_to_5x_sessions=_time_to_multiple(bar_closes, entry, 5.0),
            time_to_7x_sessions=_time_to_multiple(bar_closes, entry, 7.0),
            time_to_10x_sessions=_time_to_multiple(bar_closes, entry, 10.0),
            outcome_status=status,
            diagnostics={
                "source": anchor.source,
                "source_symbol": anchor.source_symbol,
                "terminal_consideration_used": terminal_in_horizon,
                "terminal_source_ref": (
                    terminal_consideration.source_ref
                    if terminal_in_horizon and terminal_consideration is not None
                    else None
                ),
                "terminal_time_to_multiple_status": (
                    "NOT_COMPUTED_PENDING_TRADING_CALENDAR_SPEC"
                    if terminal_in_horizon
                    else None
                ),
            },
        )
