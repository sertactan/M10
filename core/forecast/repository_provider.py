from __future__ import annotations

from datetime import datetime

from core.forecast.contracts import CalibratedForecast
from core.models.s153_v12_contracts import S153V12Result
from core.models.s153_v14_contracts import S153V14Result
from data.repositories.forecast_calibration_repository import (
    ForecastCalibrationRepository,
)


class PinnedCalibrationProvider:
    """Load an explicitly selected, validated historical calibration profile.

    Profile selection itself is intentionally external. Until an authoritative
    score/route-to-calibration mapping exists, Phase 8 must not infer a bucket.
    """

    def __init__(
        self,
        repository: ForecastCalibrationRepository,
        *,
        calibration_id: str,
    ) -> None:
        if not calibration_id.strip():
            raise ValueError("calibration_id is required")
        self.repository = repository
        self.calibration_id = calibration_id

    def calibrate(
        self,
        *,
        v12: S153V12Result,
        v14: S153V14Result,
        as_of: datetime,
        horizon_months: int,
    ) -> CalibratedForecast:
        if horizon_months != 12:
            raise ValueError("Pinned calibration supports only the 12-month horizon")
        # v12/v14 are deliberately not transformed here. A mapping from model
        # state to calibration bucket must come from an authoritative calibration spec.
        return self.repository.load_validated_profile(
            calibration_id=self.calibration_id,
            as_of=as_of,
        )
