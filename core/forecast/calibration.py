from __future__ import annotations

from datetime import datetime
from typing import Protocol

from core.forecast.contracts import CalibratedForecast
from core.models.s153_v12_contracts import S153V12Result
from core.models.s153_v14_contracts import S153V14Result


class ForecastCalibrationUnavailable(RuntimeError):
    pass


class ForecastCalibrationInvalid(RuntimeError):
    pass


class CalibrationProvider(Protocol):
    def calibrate(
        self,
        *,
        v12: S153V12Result,
        v14: S153V14Result,
        as_of: datetime,
        horizon_months: int,
    ) -> CalibratedForecast: ...


class UnavailableCalibrationProvider:
    """Production-safe default until Phase 6 calibration evidence is bound."""

    def calibrate(self, **kwargs) -> CalibratedForecast:
        raise ForecastCalibrationUnavailable(
            "Forecast probability calibration is unavailable. "
            "Phase 8 requires historically validated calibration evidence from "
            "the completed Phase 6 walk-forward / market-prevalence backtest. "
            "Do not invent scenario returns or probability mappings."
        )


def validate_calibration(calibration: CalibratedForecast, *, as_of: datetime) -> None:
    if calibration.calibration_cutoff.tzinfo is None:
        raise ForecastCalibrationInvalid("calibration_cutoff must be timezone-aware")
    if calibration.calibration_cutoff > as_of:
        raise ForecastCalibrationInvalid(
            "calibration_cutoff cannot be later than forecast as_of"
        )
    if calibration.sample_size < 1:
        raise ForecastCalibrationInvalid("calibration sample_size must be >= 1")
    if not calibration.calibration_id.strip():
        raise ForecastCalibrationInvalid("calibration_id is required")
    if not calibration.calibration_source.strip():
        raise ForecastCalibrationInvalid("calibration_source is required")

    probabilities = (
        calibration.probability_positive_return_pct,
        calibration.probability_2x_plus_pct,
        calibration.probability_5x_plus_pct,
        calibration.probability_10x_plus_pct,
        calibration.confidence_pct,
    )
    if any(value < 0.0 or value > 100.0 for value in probabilities):
        raise ForecastCalibrationInvalid("forecast probabilities/confidence must be in [0,100]")

    if not (
        calibration.probability_positive_return_pct
        >= calibration.probability_2x_plus_pct
        >= calibration.probability_5x_plus_pct
        >= calibration.probability_10x_plus_pct
    ):
        raise ForecastCalibrationInvalid(
            "magnitude probabilities must be monotone: positive >= 2X >= 5X >= 10X"
        )

    if not (
        calibration.bear_return_pct
        <= calibration.base_return_pct
        <= calibration.bull_return_pct
    ):
        raise ForecastCalibrationInvalid(
            "scenario returns must be ordered bear <= base <= bull"
        )
