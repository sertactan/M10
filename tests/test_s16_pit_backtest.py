from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from core.backtest.s16_benchmark import S16BenchmarkRow, evaluate_threshold
from core.historical.s16_controls import S16MatchSnapshot, matching_distance
from core.historical.s16_event_anchor import resolve_event_anchor
from core.historical.s16_feature_coverage import (
    S16FeatureCoverageError,
    S16_REQUIRED_FEATURES,
    assess_feature_coverage,
    build_complete_s16_input,
)
from core.historical.s16_pit_snapshot import build_match_snapshot
from core.prices.models import (
    AdjustmentStatus,
    PriceQualityStatus,
    SourcePriceBar,
)
from data.providers.massive_pit_reference import (
    MassivePITReference,
    MassivePITReferenceProvider,
)


def _bar(day: date, close: float, *, high: float | None = None, low: float | None = None, volume: float = 1_000_000) -> SourcePriceBar:
    return SourcePriceBar(
        security_id="SEC_TEST",
        source="MASSIVE",
        source_symbol="TEST",
        trade_date=day,
        open=close,
        high=close if high is None else high,
        low=close if low is None else low,
        raw_close=close,
        adjusted_close=close,
        volume=volume,
        retrieved_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        quality_status=PriceQualityStatus.PRIMARY,
        adjustment_status=AdjustmentStatus.DUAL_RAW_ADJUSTED,
    )


def test_massive_pit_reference_parser_supports_historical_share_fields() -> None:
    payload = {
        "results": {
            "ticker": "GME",
            "market_cap": 1_314_090_000,
            "weighted_shares_outstanding": 69_750_000,
            "share_class_shares_outstanding": 65_000_000,
            "sic_code": "5734",
            "sic_description": "RETAIL",
            "primary_exchange": "XNYS",
            "type": "CS",
            "active": True,
        }
    }
    result = MassivePITReferenceProvider.parse(
        payload, ticker="GME", as_of_date=date(2021, 1, 1)
    )
    assert result.market_cap == 1_314_090_000
    assert result.weighted_shares_outstanding == 69_750_000
    assert result.share_class_shares_outstanding == 65_000_000
    assert result.sic_code == "5734"


def test_pit_match_snapshot_uses_share_class_proxy_when_free_float_missing() -> None:
    start = date(2021, 1, 1)
    bars = [_bar(start + timedelta(days=i), 2.0 + i * 0.01, volume=500_000 + i * 1_000) for i in range(25)]
    ref = MassivePITReference(
        ticker="TEST",
        as_of_date=bars[-1].trade_date,
        market_cap=50_000_000,
        weighted_shares_outstanding=25_000_000,
        share_class_shares_outstanding=20_000_000,
        sic_code="7372",
        sic_description="SERVICES",
        primary_exchange="XNAS",
        security_type="CS",
        active=True,
    )
    snapshot, evidence = build_match_snapshot(
        security_id="SEC_TEST",
        ticker="TEST",
        as_of_date=bars[-1].trade_date,
        bars=bars,
        reference=ref,
        ipo_date=date(2020, 1, 1),
        ipo_route=False,
    )
    assert snapshot.float_shares == 20_000_000
    assert snapshot.supply_kind == "SHARE_CLASS_OUTSTANDING_PROXY"
    assert snapshot.market_cap == 50_000_000
    assert evidence.price_sessions == 25


def test_matching_distance_renormalizes_missing_sector() -> None:
    base = dict(
        as_of_date=date(2024, 1, 2),
        market_cap=10_000_000,
        float_shares=2_000_000,
        price=2.0,
        adv20=500_000,
        volatility20=0.08,
        mom5=0.05,
        mom20=0.10,
        listing_age_days=300,
    )
    a = S16MatchSnapshot(security_id="A", ticker="A", sector="", **base)
    b = S16MatchSnapshot(security_id="B", ticker="B", sector="TECH", **base)
    assert matching_distance(a, b) == pytest.approx(0.0)


def test_event_anchor_resolves_strict_prior_close_10x() -> None:
    start = date(2023, 10, 2)
    bars = [
        _bar(start, 1.0),
        _bar(start + timedelta(days=1), 1.2, high=2.0),
        _bar(start + timedelta(days=2), 2.0, high=11.0),
        _bar(start + timedelta(days=3), 4.0, high=8.0),
        _bar(start + timedelta(days=4), 5.0, high=7.0),
        _bar(start + timedelta(days=5), 6.0, high=6.0),
    ]
    result = resolve_event_anchor(
        ticker="TEST",
        event_period="2023-10",
        measurement_type="INTRAWEEK_HIGH",
        bars=bars,
    )
    assert result.resolution == "STRICT_PRIOR_CLOSE_TO_5D_HIGH"
    assert result.as_of_date == start
    assert result.strict_5d_10x_from_prior_close is True
    assert result.observed_multiple == pytest.approx(11.0)


def test_event_anchor_marks_intraday_only_separately() -> None:
    start = date(2023, 11, 1)
    bars = [
        _bar(start, 20.0),
        _bar(start + timedelta(days=1), 20.0, high=22.0, low=20.0),
        _bar(start + timedelta(days=2), 20.0, high=100.0, low=5.0),
        _bar(start + timedelta(days=3), 18.0),
        _bar(start + timedelta(days=4), 17.0),
        _bar(start + timedelta(days=5), 16.0),
        _bar(start + timedelta(days=6), 15.0),
    ]
    result = resolve_event_anchor(
        ticker="TEST",
        event_period="2023-11",
        measurement_type="INTRADAY_HIGH",
        bars=bars,
    )
    assert result.resolution == "INTRADAY_ONLY_NOT_STRICT_5D_PRIOR_CLOSE"
    assert result.strict_5d_10x_from_prior_close is False
    assert result.observed_multiple == pytest.approx(20.0)


def test_s16_feature_coverage_is_fail_closed() -> None:
    incomplete = {key: 50.0 for key in S16_REQUIRED_FEATURES}
    incomplete["social_velocity"] = None
    coverage = assess_feature_coverage(incomplete)
    assert coverage.score_ready is False
    assert "social_velocity" in coverage.missing
    with pytest.raises(S16FeatureCoverageError):
        build_complete_s16_input(
            security_id="SEC_TEST",
            ticker="TEST",
            as_of=datetime(2025, 1, 1, tzinfo=timezone.utc),
            route=None,
            features=incomplete,
        )


def test_s16_case_control_metrics_report_fpr_and_sample_precision() -> None:
    rows = [
        S16BenchmarkRow("p1", "POSITIVE", 70, 80, 75, 85, True, True, True, True, True, True),
        S16BenchmarkRow("p2", "POSITIVE", 40, 50, 45, 55, True, True, True, False, False, False),
        S16BenchmarkRow("c1", "CONTROL", 65, 60, 55, 60, False, False, False, False, False, False),
        S16BenchmarkRow("c2", "CONTROL", 20, 20, 20, 20, False, False, False, False, False, False),
    ]
    metrics = evaluate_threshold(
        rows,
        score_field="v03_armed",
        label_field="hit_10x_high",
        threshold=60,
    )
    assert metrics.tp == 1
    assert metrics.fn == 1
    assert metrics.fp == 0
    assert metrics.tn == 2
    assert metrics.recall == pytest.approx(0.5)
    assert metrics.false_positive_rate == pytest.approx(0.0)
    assert metrics.case_control_precision == pytest.approx(1.0)
    assert metrics.real_world_precision_available is False
