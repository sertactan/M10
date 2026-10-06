from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from core.backtest.s16_outcomes import S16FiveSessionOutcomeEngine
from core.prices.models import AdjustmentStatus, PriceQualityStatus, SourcePriceBar


def _bar(day: date, close: float, high: float | None = None) -> SourcePriceBar:
    high = close if high is None else high
    return SourcePriceBar(
        security_id="SEC_TEST",
        source="MASSIVE",
        source_symbol="TEST",
        trade_date=day,
        open=close,
        high=high,
        low=close,
        raw_close=close,
        adjusted_close=close,
        volume=1_000_000.0,
        retrieved_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        quality_status=PriceQualityStatus.PRIMARY,
        adjustment_status=AdjustmentStatus.DUAL_RAW_ADJUSTED,
    )


def test_s16_five_session_high_and_close_labels_are_separate() -> None:
    start = date(2025, 1, 1)
    bars = [_bar(start, 1.0)]
    closes = [1.4, 2.0, 2.5, 3.0, 4.0]
    highs = [1.8, 3.2, 5.2, 8.0, 10.5]
    bars.extend(
        _bar(start + timedelta(days=i), close, high)
        for i, (close, high) in enumerate(zip(closes, highs), start=1)
    )
    result = S16FiveSessionOutcomeEngine().compute(
        security_id="SEC_TEST",
        as_of_date_requested=start,
        bars=bars,
    )
    assert result.status == "READY"
    assert result.max_high_multiple_5d == 10.5
    assert result.max_close_multiple_5d == 4.0
    assert result.hit_3x_high is True
    assert result.hit_5x_high is True
    assert result.hit_10x_high is True
    assert result.hit_3x_close is True
    assert result.hit_5x_close is False
    assert result.hit_10x_close is False
