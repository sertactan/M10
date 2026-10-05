from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from core.backtest.contracts import TerminalConsideration
from core.backtest.engine import HistoricalBacktestEngine
from core.backtest.metrics import prediction_error_class
from core.backtest.outcomes import CanonicalForwardOutcomeEngine
from core.backtest.spec_manifest import Phase6SpecificationBinding
from core.models.s153_v12_contracts import S153V12Input
from core.models.s153_v14 import V14CanonicalSpecificationMissing
from core.models.s153_v14_contracts import S153V14Input
from core.prices.models import (
    AdjustmentStatus,
    PriceQualityStatus,
    SourcePriceBar,
)
from core.prices.policy import PriceSourceMixingError


def _bar(day: date, close: float, *, source: str = "MASSIVE") -> SourcePriceBar:
    return SourcePriceBar(
        security_id="SEC_TEST",
        source=source,
        source_symbol="TEST",
        trade_date=day,
        open=close,
        high=close,
        low=close,
        raw_close=close,
        adjusted_close=close,
        volume=1_000_000.0,
        retrieved_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        quality_status=PriceQualityStatus.PRIMARY,
        adjustment_status=AdjustmentStatus.DUAL_RAW_ADJUSTED,
    )


def _series(forward_closes: list[float]) -> list[SourcePriceBar]:
    start = date(2025, 1, 1)
    return [_bar(start, 10.0)] + [
        _bar(start + timedelta(days=i), close)
        for i, close in enumerate(forward_closes, start=1)
    ]


def test_fm252_uses_next_252_adjusted_closes_and_anchor_close() -> None:
    forward = [10.0] * 99 + [100.0] + [20.0] * 152
    result = CanonicalForwardOutcomeEngine().compute(
        security_id="SEC_TEST",
        as_of_date_requested=date(2025, 1, 1),
        bars=_series(forward),
    )
    assert result.outcome_status == "READY"
    assert result.horizon_sessions_available == 252
    assert result.fm252 == pytest.approx(10.0)
    assert result.outcome_class == "TRUE_10X"
    assert result.time_to_10x_sessions == 100


@pytest.mark.parametrize(
    ("max_close", "expected"),
    [
        (95.0, "NEAR_MISS_10X"),
        (60.0, "MAJOR_WINNER"),
        (40.0, "STRONG_WINNER"),
        (25.0, "MODERATE_WINNER"),
        (15.0, "FAILURE"),
    ],
)
def test_canonical_forward_classes(max_close: float, expected: str) -> None:
    forward = [10.0] * 251 + [max_close]
    result = CanonicalForwardOutcomeEngine().compute(
        security_id="SEC_TEST",
        as_of_date_requested=date(2025, 1, 1),
        bars=_series(forward),
    )
    assert result.outcome_status == "READY"
    assert result.outcome_class == expected


def test_incomplete_252_path_is_partial_not_silently_imputed() -> None:
    result = CanonicalForwardOutcomeEngine().compute(
        security_id="SEC_TEST",
        as_of_date_requested=date(2025, 1, 1),
        bars=_series([20.0] * 10),
    )
    assert result.outcome_status == "PARTIAL"
    assert result.fm252 is None
    assert result.outcome_class is None
    assert result.max_multiple_observed == pytest.approx(2.0)


def test_unknown_terminal_value_is_censored() -> None:
    result = CanonicalForwardOutcomeEngine().compute(
        security_id="SEC_TEST",
        as_of_date_requested=date(2025, 1, 1),
        bars=_series([20.0] * 10),
        terminal_value_unknown=True,
    )
    assert result.outcome_status == "CENSORED"
    assert result.fm252 is None
    assert result.outcome_class is None


def test_verified_terminal_consideration_closes_outcome_path() -> None:
    terminal = TerminalConsideration(
        effective_date=date(2025, 1, 20),
        value_per_share=50.0,
        source_ref="canonical-corporate-action-record",
        verified_within_252_session_horizon=True,
    )
    result = CanonicalForwardOutcomeEngine().compute(
        security_id="SEC_TEST",
        as_of_date_requested=date(2025, 1, 1),
        bars=_series([12.0] * 10),
        terminal_consideration=terminal,
    )
    assert result.outcome_status == "READY"
    assert result.fm252 == pytest.approx(5.0)
    assert result.outcome_class == "MAJOR_WINNER"
    assert result.diagnostics["terminal_consideration_used"] is True
    assert result.time_to_5x_sessions is None


def test_terminal_value_is_not_used_without_verified_horizon() -> None:
    terminal = TerminalConsideration(
        effective_date=date(2025, 1, 20),
        value_per_share=100.0,
        source_ref="unverified-calendar-placement",
        verified_within_252_session_horizon=False,
    )
    result = CanonicalForwardOutcomeEngine().compute(
        security_id="SEC_TEST",
        as_of_date_requested=date(2025, 1, 1),
        bars=_series([12.0] * 10),
        terminal_consideration=terminal,
    )
    assert result.outcome_status == "PARTIAL"
    assert result.fm252 is None
    assert result.diagnostics["terminal_consideration_used"] is False


def test_cross_provider_price_stitching_is_rejected() -> None:
    bars = _series([20.0] * 252)
    bars[-1] = _bar(bars[-1].trade_date, 20.0, source="STOOQ")
    with pytest.raises(PriceSourceMixingError):
        CanonicalForwardOutcomeEngine().compute(
            security_id="SEC_TEST",
            as_of_date_requested=date(2025, 1, 1),
            bars=bars,
        )


def test_prediction_error_classes_exclude_non_ready() -> None:
    ready = CanonicalForwardOutcomeEngine().compute(
        security_id="SEC_TEST",
        as_of_date_requested=date(2025, 1, 1),
        bars=_series([10.0] * 251 + [20.0]),
    )
    assert prediction_error_class(
        precision_confirmed=True,
        outcome=ready,
    ) == "HARD_FP"

    partial = CanonicalForwardOutcomeEngine().compute(
        security_id="SEC_TEST",
        as_of_date_requested=date(2025, 1, 1),
        bars=_series([20.0]),
    )
    assert prediction_error_class(
        precision_confirmed=True,
        outcome=partial,
    ) is None


def test_phase6_binding_lists_all_authoritative_sources_when_unbound() -> None:
    binding = Phase6SpecificationBinding()
    assert binding.complete is False
    assert len(binding.missing()) == 6


def test_full_backtest_cannot_bypass_incomplete_phase5() -> None:
    as_of = datetime(2025, 1, 1, tzinfo=timezone.utc)
    v12 = S153V12Input(
        security_id="SEC_TEST",
        ticker="TEST",
        as_of=as_of,
        discovery_factors={},
        control_factors={},
        features={},
    )
    v14 = S153V14Input(
        security_id="SEC_TEST",
        ticker="TEST",
        as_of=as_of,
        discovery_factors={},
        control_factors={},
        features={},
    )
    with pytest.raises(V14CanonicalSpecificationMissing):
        HistoricalBacktestEngine().evaluate(
            v12_input=v12,
            v14_input=v14,
            bars=_series([20.0] * 252),
        )
