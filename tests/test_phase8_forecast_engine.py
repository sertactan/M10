from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from core.forecast.calibration import (
    ForecastCalibrationInvalid,
    ForecastCalibrationUnavailable,
)
from core.forecast.contracts import CalibratedForecast
from core.forecast.engine import ForecastEngine, ForecastModeError
from core.scanner.contracts import ScanCandidate


AS_OF = datetime(2026, 10, 6, 9, 0, tzinfo=timezone.utc)
TODAY = date(2026, 10, 6)
CANDIDATE = ScanCandidate(
    security_id="SEC_TEST",
    ticker="TEST",
    exchange="NASDAQ",
)


class FakeScorer:
    def score(self, candidate, as_of):
        assert candidate == CANDIDATE
        return (
            SimpleNamespace(score=81.0, status="READY"),
            SimpleNamespace(score=87.0, status="READY"),
        )


class ValidCalibration:
    def calibrate(self, **kwargs):
        return CalibratedForecast(
            calibration_id="CAL-001",
            calibration_source="PHASE6_MARKET_PREVALENCE_WALK_FORWARD",
            calibration_cutoff=AS_OF - timedelta(days=1),
            sample_size=1250,
            bull_return_pct=180.0,
            base_return_pct=65.0,
            bear_return_pct=-35.0,
            probability_positive_return_pct=74.0,
            probability_2x_plus_pct=31.0,
            probability_5x_plus_pct=8.0,
            probability_10x_plus_pct=2.0,
            confidence_pct=82.0,
            risk="MEDIUM",
            metadata={"evidence": "test-only calibration fixture"},
        )


def test_forward_forecast_uses_calibrated_values_and_explicit_disclosure():
    result = ForecastEngine(FakeScorer(), ValidCalibration()).forecast(
        candidate=CANDIDATE,
        as_of=AS_OF,
        current_date=TODAY,
    )
    assert result.horizon_months == 12
    assert result.v12_score == 81.0
    assert result.v14_score == 87.0
    assert result.bull_return_pct == 180.0
    assert result.base_return_pct == 65.0
    assert result.bear_return_pct == -35.0
    assert result.probability_positive_return_pct == 74.0
    assert result.probability_2x_plus_pct == 31.0
    assert result.probability_5x_plus_pct == 8.0
    assert result.probability_10x_plus_pct == 2.0
    assert "not a realized outcome" in result.disclosure


def test_forecast_fails_closed_without_calibration_provider():
    with pytest.raises(ForecastCalibrationUnavailable):
        ForecastEngine(FakeScorer()).forecast(
            candidate=CANDIDATE,
            as_of=AS_OF,
            current_date=TODAY,
        )


def test_forecast_rejects_non_current_analysis_date():
    with pytest.raises(ForecastModeError, match="current date"):
        ForecastEngine(FakeScorer(), ValidCalibration()).forecast(
            candidate=CANDIDATE,
            as_of=AS_OF,
            current_date=date(2026, 10, 5),
        )


def test_forecast_rejects_non_12_month_horizon():
    with pytest.raises(ForecastModeError, match="12-month"):
        ForecastEngine(FakeScorer(), ValidCalibration()).forecast(
            candidate=CANDIDATE,
            as_of=AS_OF,
            current_date=TODAY,
            horizon_months=6,
        )


def test_forecast_rejects_future_calibration_cutoff():
    class FutureCalibration(ValidCalibration):
        def calibrate(self, **kwargs):
            base = super().calibrate(**kwargs)
            return CalibratedForecast(
                **{
                    **base.__dict__,
                    "calibration_cutoff": AS_OF + timedelta(seconds=1),
                }
            )

    with pytest.raises(ForecastCalibrationInvalid, match="later than forecast"):
        ForecastEngine(FakeScorer(), FutureCalibration()).forecast(
            candidate=CANDIDATE,
            as_of=AS_OF,
            current_date=TODAY,
        )


def test_forecast_rejects_non_monotone_magnitude_probabilities():
    class InvalidProbabilities(ValidCalibration):
        def calibrate(self, **kwargs):
            base = super().calibrate(**kwargs)
            return CalibratedForecast(
                **{
                    **base.__dict__,
                    "probability_5x_plus_pct": 40.0,
                }
            )

    with pytest.raises(ForecastCalibrationInvalid, match="monotone"):
        ForecastEngine(FakeScorer(), InvalidProbabilities()).forecast(
            candidate=CANDIDATE,
            as_of=AS_OF,
            current_date=TODAY,
        )


def test_forecast_rejects_misordered_scenarios():
    class InvalidScenarios(ValidCalibration):
        def calibrate(self, **kwargs):
            base = super().calibrate(**kwargs)
            return CalibratedForecast(
                **{
                    **base.__dict__,
                    "bear_return_pct": 100.0,
                }
            )

    with pytest.raises(ForecastCalibrationInvalid, match="bear <= base <= bull"):
        ForecastEngine(FakeScorer(), InvalidScenarios()).forecast(
            candidate=CANDIDATE,
            as_of=AS_OF,
            current_date=TODAY,
        )
