from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from core.forecast.contracts import ForecastResult
from data.database.sqlite_store import SQLiteStore


class ForecastReproducibilityError(RuntimeError):
    pass


@dataclass(frozen=True)
class ForecastRunReceipt:
    analysis_id: str
    forecast_hash: str
    calibration_evidence_hash: str


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _require_sha256(name: str, value: str) -> str:
    normalized = value.strip().lower()
    if len(normalized) != 64 or any(c not in "0123456789abcdef" for c in normalized):
        raise ForecastReproducibilityError(f"{name} must be a SHA-256 hex digest")
    return normalized


class ForecastRunRepository:
    """Persist reproducible Phase 8 forecast runs.

    The repository does not compute model scores, probabilities, or scenarios.
    It verifies that the forecast is tied to a validated calibration profile and
    records the immutable inputs/provenance required to reproduce the result.
    """

    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def save(
        self,
        *,
        result: ForecastResult,
        v12_model_version: str,
        v14_model_version: str,
        data_snapshot_hash: str,
        model_config_hash: str,
    ) -> ForecastRunReceipt:
        if result.as_of.tzinfo is None:
            raise ForecastReproducibilityError("forecast as_of must be timezone-aware")
        if result.horizon_months != 12:
            raise ForecastReproducibilityError("Phase 8 forecast persistence requires 12 months")
        if not v12_model_version.strip() or not v14_model_version.strip():
            raise ForecastReproducibilityError("both model versions are required")

        data_snapshot_hash = _require_sha256("data_snapshot_hash", data_snapshot_hash)
        model_config_hash = _require_sha256("model_config_hash", model_config_hash)

        calibration = self.store.connection.execute(
            """
            SELECT *
            FROM forecast_calibration_profiles
            WHERE calibration_id=? AND status='VALIDATED'
            LIMIT 1
            """,
            (result.calibration_id,),
        ).fetchone()
        if calibration is None:
            raise ForecastReproducibilityError(
                f"Validated calibration profile is unavailable: {result.calibration_id}"
            )

        evidence_json = str(calibration["evidence_json"])
        evidence_hash = hashlib.sha256(evidence_json.encode("utf-8")).hexdigest()
        if evidence_hash != calibration["evidence_hash"]:
            raise ForecastReproducibilityError(
                f"Calibration evidence hash mismatch: {result.calibration_id}"
            )

        result_evidence_hash = str(
            result.calibration_metadata.get("evidence_hash") or ""
        ).strip().lower()
        if result_evidence_hash != evidence_hash:
            raise ForecastReproducibilityError(
                "Forecast result calibration provenance does not match persisted evidence"
            )

        persisted_cutoff = datetime.fromisoformat(str(calibration["calibration_cutoff"]))
        if persisted_cutoff != result.calibration_cutoff:
            raise ForecastReproducibilityError("calibration cutoff mismatch")
        if int(calibration["sample_size"]) != result.calibration_sample_size:
            raise ForecastReproducibilityError("calibration sample size mismatch")

        payload = {
            "security_id": result.security_id,
            "ticker": result.ticker,
            "analysis_date": result.as_of.astimezone(timezone.utc).isoformat(),
            "horizon_months": result.horizon_months,
            "v12_model_version": v12_model_version,
            "v14_model_version": v14_model_version,
            "v12_score": result.v12_score,
            "v12_status": result.v12_status,
            "v12_route": result.v12_route,
            "v12_destination": result.v12_destination,
            "v14_score": result.v14_score,
            "v14_status": result.v14_status,
            "v14_route": result.v14_route,
            "v14_destination": result.v14_destination,
            "bull_return_pct": result.bull_return_pct,
            "base_return_pct": result.base_return_pct,
            "bear_return_pct": result.bear_return_pct,
            "probability_positive_return_pct": result.probability_positive_return_pct,
            "probability_2x_plus_pct": result.probability_2x_plus_pct,
            "probability_5x_plus_pct": result.probability_5x_plus_pct,
            "probability_10x_plus_pct": result.probability_10x_plus_pct,
            "confidence_pct": result.confidence_pct,
            "risk": result.risk,
            "calibration_id": result.calibration_id,
            "calibration_source": result.calibration_source,
            "calibration_cutoff": result.calibration_cutoff.isoformat(),
            "calibration_sample_size": result.calibration_sample_size,
            "calibration_evidence_hash": evidence_hash,
            "data_snapshot_hash": data_snapshot_hash,
            "model_config_hash": model_config_hash,
            "disclosure": result.disclosure,
        }
        forecast_payload_json = _stable_json(payload)
        forecast_hash = hashlib.sha256(
            forecast_payload_json.encode("utf-8")
        ).hexdigest()
        analysis_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                "|".join(
                    (
                        result.security_id,
                        payload["analysis_date"],
                        v12_model_version,
                        v14_model_version,
                        data_snapshot_hash,
                        model_config_hash,
                        result.calibration_id,
                        forecast_hash,
                    )
                ),
            )
        )
        created_at = datetime.now(timezone.utc).isoformat()

        self.store.connection.execute(
            """
            INSERT INTO forecast_runs (
                analysis_id,security_id,ticker,analysis_date,horizon_months,
                v12_model_version,v14_model_version,v12_score,v14_score,
                v12_route,v14_route,v12_destination,v14_destination,
                calibration_id,calibration_cutoff,calibration_sample_size,
                calibration_evidence_hash,data_snapshot_hash,model_config_hash,
                forecast_payload_json,forecast_hash,created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(analysis_id) DO UPDATE SET
                forecast_payload_json=excluded.forecast_payload_json,
                forecast_hash=excluded.forecast_hash,
                created_at=excluded.created_at
            """,
            (
                analysis_id,
                result.security_id,
                result.ticker,
                payload["analysis_date"],
                result.horizon_months,
                v12_model_version,
                v14_model_version,
                result.v12_score,
                result.v14_score,
                result.v12_route,
                result.v14_route,
                result.v12_destination,
                result.v14_destination,
                result.calibration_id,
                result.calibration_cutoff.isoformat(),
                result.calibration_sample_size,
                evidence_hash,
                data_snapshot_hash,
                model_config_hash,
                forecast_payload_json,
                forecast_hash,
                created_at,
            ),
        )
        self.store.connection.commit()
        return ForecastRunReceipt(
            analysis_id=analysis_id,
            forecast_hash=forecast_hash,
            calibration_evidence_hash=evidence_hash,
        )

    def load(self, analysis_id: str) -> dict[str, Any]:
        row = self.store.connection.execute(
            "SELECT * FROM forecast_runs WHERE analysis_id=?",
            (analysis_id,),
        ).fetchone()
        if row is None:
            raise ForecastReproducibilityError(
                f"Forecast run not found: {analysis_id}"
            )
        payload = json.loads(row["forecast_payload_json"])
        actual_hash = hashlib.sha256(
            _stable_json(payload).encode("utf-8")
        ).hexdigest()
        if actual_hash != row["forecast_hash"]:
            raise ForecastReproducibilityError(
                f"Forecast payload hash mismatch: {analysis_id}"
            )
        return {**dict(row), "forecast_payload": payload}
