from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Iterable, Mapping

from core.prices.models import SourcePriceBar
from core.prices.policy import PriceSelectionPolicy


@dataclass(frozen=True)
class S16ForwardOutcome:
    security_id: str
    as_of_date_requested: date
    anchor_session: date | None
    entry_adjusted_close: float | None
    horizon_sessions_available: int
    max_high_multiple_5d: float | None
    max_close_multiple_5d: float | None
    hit_3x_high: bool | None
    hit_5x_high: bool | None
    hit_10x_high: bool | None
    hit_3x_close: bool | None
    hit_5x_close: bool | None
    hit_10x_close: bool | None
    status: str
    diagnostics: Mapping[str, object] = field(default_factory=dict)


def _adjusted_high(bar: SourcePriceBar) -> float | None:
    raw_close = float(bar.raw_close)
    high = float(bar.high)
    adjusted_close = float(bar.adjusted_close)
    if raw_close <= 0 or high <= 0 or adjusted_close <= 0:
        return None
    return high * (adjusted_close / raw_close)


class S16FiveSessionOutcomeEngine:
    """Leakage-safe 1-5 trading-session outcomes for 3x/5x/10x labels."""

    def compute(
        self,
        *,
        security_id: str,
        as_of_date_requested: date,
        bars: Iterable[SourcePriceBar],
    ) -> S16ForwardOutcome:
        ordered = sorted(list(bars), key=lambda b: b.trade_date)
        if not ordered:
            return self._invalid(security_id, as_of_date_requested, "no bars")
        PriceSelectionPolicy.assert_single_source(ordered)
        if {b.security_id for b in ordered} != {security_id}:
            return self._invalid(security_id, as_of_date_requested, "identity mismatch")

        completed = [b for b in ordered if b.trade_date <= as_of_date_requested]
        if not completed:
            return self._invalid(security_id, as_of_date_requested, "no anchor session")
        anchor = completed[-1]
        entry = float(anchor.adjusted_close)
        if entry <= 0:
            return self._invalid(security_id, as_of_date_requested, "non-positive entry")

        forward = [b for b in ordered if b.trade_date > anchor.trade_date][:5]
        if not forward:
            return S16ForwardOutcome(
                security_id=security_id,
                as_of_date_requested=as_of_date_requested,
                anchor_session=anchor.trade_date,
                entry_adjusted_close=entry,
                horizon_sessions_available=0,
                max_high_multiple_5d=None,
                max_close_multiple_5d=None,
                hit_3x_high=None, hit_5x_high=None, hit_10x_high=None,
                hit_3x_close=None, hit_5x_close=None, hit_10x_close=None,
                status="PARTIAL",
                diagnostics={"reason": "no forward sessions"},
            )

        highs = [x for b in forward if (x := _adjusted_high(b)) is not None]
        closes = [float(b.adjusted_close) for b in forward if float(b.adjusted_close) > 0]
        high_multiple = max(highs) / entry if highs else None
        close_multiple = max(closes) / entry if closes else None
        status = "READY" if len(forward) == 5 else "PARTIAL"

        def hit(value: float | None, threshold: float) -> bool | None:
            return None if value is None else value >= threshold

        return S16ForwardOutcome(
            security_id=security_id,
            as_of_date_requested=as_of_date_requested,
            anchor_session=anchor.trade_date,
            entry_adjusted_close=entry,
            horizon_sessions_available=len(forward),
            max_high_multiple_5d=high_multiple,
            max_close_multiple_5d=close_multiple,
            hit_3x_high=hit(high_multiple, 3.0),
            hit_5x_high=hit(high_multiple, 5.0),
            hit_10x_high=hit(high_multiple, 10.0),
            hit_3x_close=hit(close_multiple, 3.0),
            hit_5x_close=hit(close_multiple, 5.0),
            hit_10x_close=hit(close_multiple, 10.0),
            status=status,
            diagnostics={
                "source": anchor.source,
                "source_symbol": anchor.source_symbol,
                "high_adjustment": "high * adjusted_close/raw_close",
                "horizon": "next_5_trading_sessions",
            },
        )

    @staticmethod
    def _invalid(security_id: str, requested: date, reason: str) -> S16ForwardOutcome:
        return S16ForwardOutcome(
            security_id=security_id,
            as_of_date_requested=requested,
            anchor_session=None,
            entry_adjusted_close=None,
            horizon_sessions_available=0,
            max_high_multiple_5d=None,
            max_close_multiple_5d=None,
            hit_3x_high=None, hit_5x_high=None, hit_10x_high=None,
            hit_3x_close=None, hit_5x_close=None, hit_10x_close=None,
            status="INVALID",
            diagnostics={"reason": reason},
        )
