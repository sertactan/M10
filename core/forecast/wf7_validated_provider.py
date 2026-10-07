from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from core.forecast.calibration import ForecastCalibrationUnavailable


@dataclass(frozen=True)
class WF7ValidatedMagnitudeCalibration:
    calibration_id: str
    hardening_id: str
    wf7_run_id: str
    wf6_run_id: str
    calibration_cutoff: datetime
    bucket_label: str
    sample_size: int
    sample_quality: str
    probability_2x_plus_pct: float
    probability_5x_plus_pct: float
    probability_7x_plus_pct: float
    probability_10x_plus_pct: float
    model_version: str = "S15.3_V1.4.1"
    source: str = "WF7_OOS_MARKET_PREVALENCE_VALIDATED"


SCORE_BUCKETS = (
    (0.0,55.0,"<55"),
    (55.0,65.0,"55-64"),
    (65.0,75.0,"65-74"),
    (75.0,80.0,"75-79"),
    (80.0,85.0,"80-84"),
    (85.0,101.0,"85+"),
)


def score_bucket(score: float) -> tuple[float,float,str] | None:
    for low,high,label in SCORE_BUCKETS:
        if low <= float(score) < high:
            return low,high,label
    return None


class WF7ValidatedMagnitudeCalibrationProvider:
    """Production magnitude calibration bound only to hardened WF7 OOS evidence.

    This provider intentionally exposes only empirical magnitude frequencies.
    It does not manufacture positive-return probability or bear/base/bull return
    scenarios because WF7 does not currently validate those outputs.
    """

    def __init__(self, store) -> None:
        self.store=store

    def _latest_hardened_chain(self):
        return self.store.connection.execute(
            """
            SELECT h.*,v.model_version
            FROM wf8_hardening_runs h
            JOIN wf7_validation_runs v ON v.run_id=h.wf7_run_id
            WHERE h.status='PRODUCTION_EVIDENCE_READY'
              AND v.status='COMPLETE'
              AND v.model_version='S15.3_V1.4.1'
            ORDER BY h.created_at DESC
            LIMIT 1
            """
        ).fetchone()

    def calibrate(
        self,
        *,
        score: float | None,
        as_of: datetime,
    ) -> WF7ValidatedMagnitudeCalibration:
        if as_of.tzinfo is None:
            raise ValueError("forecast as_of must be timezone-aware")
        if score is None:
            raise ForecastCalibrationUnavailable("V1.4.1 score is unavailable")

        bucket=score_bucket(float(score))
        if bucket is None:
            raise ForecastCalibrationUnavailable(
                f"No WF7 score bucket exists for score={score}"
            )
        _low,_high,label=bucket

        chain=self._latest_hardened_chain()
        if chain is None:
            raise ForecastCalibrationUnavailable(
                "No WF8 PRODUCTION_EVIDENCE_READY chain exists for S15.3 V1.4.1"
            )

        wf7_run_id=str(chain["wf7_run_id"])
        wf6_run_id=str(chain["wf6_run_id"])
        bucket_row=self.store.connection.execute(
            """
            SELECT *
            FROM wf7_calibration_buckets
            WHERE run_id=? AND bucket_label=?
            LIMIT 1
            """,
            (wf7_run_id,label),
        ).fetchone()
        if bucket_row is None:
            raise ForecastCalibrationUnavailable(
                f"WF7 calibration bucket missing: {label}"
            )
        if str(bucket_row["status"]) != "READY" or int(bucket_row["sample_size"]) < 30:
            raise ForecastCalibrationUnavailable(
                f"WF7 calibration bucket not releasable: {label}; "
                f"N={bucket_row['sample_size']} status={bucket_row['status']}"
            )

        values=(
            bucket_row["p2_plus_pct"],
            bucket_row["p5_plus_pct"],
            bucket_row["p7_plus_pct"],
            bucket_row["p10_plus_pct"],
        )
        if any(value is None for value in values):
            raise ForecastCalibrationUnavailable(
                f"WF7 calibration bucket has incomplete magnitude probabilities: {label}"
            )
        p2,p5,p7,p10=(float(value) for value in values)
        if not (100.0 >= p2 >= p5 >= p7 >= p10 >= 0.0):
            raise ForecastCalibrationUnavailable(
                f"WF7 magnitude probabilities are invalid/non-monotone: {label}"
            )

        cutoff_row=self.store.connection.execute(
            """
            SELECT MAX(test_end_date) AS cutoff
            FROM wf6_walk_forward_folds
            WHERE run_id=? AND status='COMPLETE'
            """,
            (wf6_run_id,),
        ).fetchone()
        cutoff_raw=cutoff_row["cutoff"] if cutoff_row is not None else None
        if not cutoff_raw:
            raise ForecastCalibrationUnavailable("WF6 calibration cutoff is unavailable")
        cutoff=datetime.fromisoformat(str(cutoff_raw)+"T23:59:59+00:00")
        if cutoff > as_of.astimezone(timezone.utc):
            raise ForecastCalibrationUnavailable(
                "WF7 calibration cutoff is later than forecast as_of"
            )

        return WF7ValidatedMagnitudeCalibration(
            calibration_id=f"WF7-{wf7_run_id}-{label}",
            hardening_id=str(chain["hardening_id"]),
            wf7_run_id=wf7_run_id,
            wf6_run_id=wf6_run_id,
            calibration_cutoff=cutoff,
            bucket_label=label,
            sample_size=int(bucket_row["sample_size"]),
            sample_quality=str(bucket_row["sample_quality"]),
            probability_2x_plus_pct=p2,
            probability_5x_plus_pct=p5,
            probability_7x_plus_pct=p7,
            probability_10x_plus_pct=p10,
        )
