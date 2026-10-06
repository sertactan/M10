from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from core.forecast.calibration import ForecastCalibrationInvalid, validate_calibration
from core.forecast.contracts import CalibratedForecast
from data.database.sqlite_store import SQLiteStore


class CalibrationEvidenceError(RuntimeError):
    pass


class CalibrationProfileUnavailable(RuntimeError):
    pass


REQUIRED_EVIDENCE_FLAGS = (
    "walk_forward_pass",
    "leakage_audit_pass",
    "survivorship_audit_pass",
)


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


class ForecastCalibrationRepository:
    """Persist only externally-computed, audited calibration outputs.

    This repository never fits a calibration model and never derives probabilities.
    It only validates provenance/integrity gates and stores upstream outputs.
    """

    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def save_validated_profile(
        self,
        *,
        run_id: str,
        model_version: str,
        horizon_months: int,
        dataset_kind: str,
        calibration_method: str,
        calibration: CalibratedForecast,
        evidence: dict[str, Any],
    ) -> str:
        if dataset_kind != "MARKET_PREVALENCE":
            raise CalibrationEvidenceError(
                "Probability calibration requires MARKET_PREVALENCE evidence"
            )
        if not calibration_method.strip():
            raise CalibrationEvidenceError("calibration_method is required")
        if horizon_months != 12:
            raise CalibrationEvidenceError("Phase 8 calibration currently requires 12 months")

        validate_calibration(calibration, as_of=calibration.calibration_cutoff)

        missing_flags = [
            name for name in REQUIRED_EVIDENCE_FLAGS if evidence.get(name) is not True
        ]
        if missing_flags:
            raise CalibrationEvidenceError(
                "Calibration evidence is missing required PASS flags: "
                + ", ".join(missing_flags)
            )

        if evidence.get("future_outcome_in_feature_matrix") is not False:
            raise CalibrationEvidenceError(
                "Calibration evidence must prove future outcome columns are absent "
                "from the feature matrix"
            )

        run = self.store.connection.execute(
            "SELECT * FROM backtest_run_manifest WHERE run_id=?",
            (run_id,),
        ).fetchone()
        if run is None:
            raise CalibrationEvidenceError(
                f"Backtest run does not exist: {run_id}"
            )
        if str(run["status"]).upper() == "INVALID_BACKTEST":
            raise CalibrationEvidenceError(
                "INVALID_BACKTEST runs cannot be used for forecast calibration"
            )

        evidence_payload = {
            **evidence,
            "run_id": run_id,
            "model_version": model_version,
            "dataset_kind": dataset_kind,
            "calibration_method": calibration_method,
            "calibration_id": calibration.calibration_id,
            "calibration_source": calibration.calibration_source,
            "calibration_cutoff": calibration.calibration_cutoff.isoformat(),
            "sample_size": calibration.sample_size,
        }
        evidence_json = _stable_json(evidence_payload)
        evidence_hash = hashlib.sha256(evidence_json.encode("utf-8")).hexdigest()
        now = datetime.now(timezone.utc).isoformat()

        self.store.connection.execute(
            """
            INSERT INTO forecast_calibration_profiles (
                calibration_id,run_id,model_version,horizon_months,dataset_kind,
                calibration_method,calibration_cutoff,sample_size,
                bull_return_pct,base_return_pct,bear_return_pct,
                probability_positive_return_pct,probability_2x_plus_pct,
                probability_5x_plus_pct,probability_10x_plus_pct,
                confidence_pct,risk,evidence_json,evidence_hash,status,created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(calibration_id) DO UPDATE SET
                run_id=excluded.run_id,
                model_version=excluded.model_version,
                horizon_months=excluded.horizon_months,
                dataset_kind=excluded.dataset_kind,
                calibration_method=excluded.calibration_method,
                calibration_cutoff=excluded.calibration_cutoff,
                sample_size=excluded.sample_size,
                bull_return_pct=excluded.bull_return_pct,
                base_return_pct=excluded.base_return_pct,
                bear_return_pct=excluded.bear_return_pct,
                probability_positive_return_pct=excluded.probability_positive_return_pct,
                probability_2x_plus_pct=excluded.probability_2x_plus_pct,
                probability_5x_plus_pct=excluded.probability_5x_plus_pct,
                probability_10x_plus_pct=excluded.probability_10x_plus_pct,
                confidence_pct=excluded.confidence_pct,
                risk=excluded.risk,
                evidence_json=excluded.evidence_json,
                evidence_hash=excluded.evidence_hash,
                status=excluded.status,
                created_at=excluded.created_at
            """,
            (
                calibration.calibration_id,
                run_id,
                model_version,
                horizon_months,
                dataset_kind,
                calibration_method,
                calibration.calibration_cutoff.isoformat(),
                calibration.sample_size,
                calibration.bull_return_pct,
                calibration.base_return_pct,
                calibration.bear_return_pct,
                calibration.probability_positive_return_pct,
                calibration.probability_2x_plus_pct,
                calibration.probability_5x_plus_pct,
                calibration.probability_10x_plus_pct,
                calibration.confidence_pct,
                calibration.risk,
                evidence_json,
                evidence_hash,
                "VALIDATED",
                now,
            ),
        )
        self.store.connection.commit()
        return evidence_hash

    def load_validated_profile(
        self,
        *,
        calibration_id: str,
        as_of: datetime,
    ) -> CalibratedForecast:
        if as_of.tzinfo is None:
            raise ValueError("forecast as_of must be timezone-aware")

        row = self.store.connection.execute(
            """
            SELECT *
            FROM forecast_calibration_profiles
            WHERE calibration_id=?
              AND status='VALIDATED'
              AND dataset_kind='MARKET_PREVALENCE'
              AND calibration_cutoff<=?
            LIMIT 1
            """,
            (calibration_id, as_of.astimezone(timezone.utc).isoformat()),
        ).fetchone()
        if row is None:
            raise CalibrationProfileUnavailable(
                f"No validated calibration profile is available: {calibration_id}"
            )

        evidence = json.loads(row["evidence_json"])
        actual_hash = hashlib.sha256(
            _stable_json(evidence).encode("utf-8")
        ).hexdigest()
        if actual_hash != row["evidence_hash"]:
            raise CalibrationEvidenceError(
                f"Calibration evidence hash mismatch: {calibration_id}"
            )

        profile = CalibratedForecast(
            calibration_id=row["calibration_id"],
            calibration_source=evidence.get("calibration_source") or row["run_id"],
            calibration_cutoff=datetime.fromisoformat(row["calibration_cutoff"]),
            sample_size=int(row["sample_size"]),
            bull_return_pct=float(row["bull_return_pct"]),
            base_return_pct=float(row["base_return_pct"]),
            bear_return_pct=float(row["bear_return_pct"]),
            probability_positive_return_pct=float(row["probability_positive_return_pct"]),
            probability_2x_plus_pct=float(row["probability_2x_plus_pct"]),
            probability_5x_plus_pct=float(row["probability_5x_plus_pct"]),
            probability_10x_plus_pct=float(row["probability_10x_plus_pct"]),
            confidence_pct=float(row["confidence_pct"]),
            risk=str(row["risk"]),
            metadata={
                "run_id": row["run_id"],
                "model_version": row["model_version"],
                "dataset_kind": row["dataset_kind"],
                "calibration_method": row["calibration_method"],
                "evidence_hash": row["evidence_hash"],
                **evidence,
            },
        )
        validate_calibration(profile, as_of=as_of)
        return profile
