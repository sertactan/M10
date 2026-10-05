from __future__ import annotations

from datetime import date, datetime

from core.forecast.calibration import (
    CalibrationProvider,
    UnavailableCalibrationProvider,
    validate_calibration,
)
from core.forecast.contracts import FORECAST_DISCLOSURE, ForecastResult
from core.scanner.contracts import ScanCandidate
from core.scanner.production import SecurityScorer


class ForecastModeError(RuntimeError):
    pass


class ForecastEngine:
    """Current-date / 12M forward forecast orchestrator.

    Model scores come from the canonical Phase 4/5 engines through SecurityScorer.
    Probability and scenario values come only from a calibration provider backed
    by historical Phase 6 evidence. No probability mapping lives in this class.
    """

    def __init__(
        self,
        scorer: SecurityScorer,
        calibration_provider: CalibrationProvider | None = None,
    ) -> None:
        self.scorer = scorer
        self.calibration_provider = (
            calibration_provider or UnavailableCalibrationProvider()
        )

    def forecast(
        self,
        *,
        candidate: ScanCandidate,
        as_of: datetime,
        current_date: date,
        horizon_months: int = 12,
    ) -> ForecastResult:
        if as_of.tzinfo is None:
            raise ValueError("forecast as_of must be timezone-aware")
        if as_of.date() != current_date:
            raise ForecastModeError(
                "Phase 8 current/forward mode requires the selected analysis date "
                "to equal the application's current date"
            )
        if horizon_months != 12:
            raise ForecastModeError(
                "Phase 8 canonical scope currently supports only the 12-month horizon"
            )

        v12, v14 = self.scorer.score(candidate, as_of)
        calibration = self.calibration_provider.calibrate(
            v12=v12,
            v14=v14,
            as_of=as_of,
            horizon_months=horizon_months,
        )
        validate_calibration(calibration, as_of=as_of)

        return ForecastResult(
            security_id=candidate.security_id,
            ticker=candidate.ticker,
            as_of=as_of,
            horizon_months=horizon_months,
            v12_score=v12.score,
            v12_status=v12.status,
            v14_score=v14.score,
            v14_status=v14.status,
            bull_return_pct=calibration.bull_return_pct,
            base_return_pct=calibration.base_return_pct,
            bear_return_pct=calibration.bear_return_pct,
            probability_positive_return_pct=calibration.probability_positive_return_pct,
            probability_2x_plus_pct=calibration.probability_2x_plus_pct,
            probability_5x_plus_pct=calibration.probability_5x_plus_pct,
            probability_10x_plus_pct=calibration.probability_10x_plus_pct,
            confidence_pct=calibration.confidence_pct,
            risk=calibration.risk,
            calibration_id=calibration.calibration_id,
            calibration_source=calibration.calibration_source,
            calibration_cutoff=calibration.calibration_cutoff,
            calibration_sample_size=calibration.sample_size,
            disclosure=FORECAST_DISCLOSURE,
        )
