from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable

from data.database.sqlite_store import SQLiteStore


ALLOWED_SOURCE_PHASES = {
    "PHASE1_UNIVERSE",
    "PHASE2_PRICE",
    "PHASE3_FUNDAMENTAL",
    "HISTORICAL_CONTROLS",
    "DERIVED_CANONICAL",
}


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return dt.astimezone(timezone.utc).isoformat()


class ModelFeatureRepository:
    """PIT model-feature materialization. This is not a data provider.

    Rows must trace to Phase 1-3 canonical storage, historical-control datasets,
    or deterministic derivations from those rows.
    """

    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def save_feature(
        self,
        *,
        security_id: str,
        feature_key: str,
        value: float | None,
        feature_as_of: datetime,
        available_at: datetime,
        source_phase: str,
        source_ref: str,
        quality_status: str,
        computation_version: str,
        evidence: dict[str, Any] | None = None,
    ) -> str:
        if source_phase not in ALLOWED_SOURCE_PHASES:
            raise ValueError(
                f"Canonical model layer forbids non-canonical source phase: {source_phase}"
            )
        if available_at > feature_as_of:
            # A feature snapshot cannot claim knowledge before its latest input existed.
            raise ValueError("available_at cannot be later than feature_as_of")
        feature_id = str(uuid.uuid5(
            uuid.NAMESPACE_URL,
            "|".join([
                security_id, feature_key, _iso(feature_as_of), source_phase,
                source_ref, computation_version,
            ]),
        ))
        self.store.connection.execute(
            """
            INSERT INTO canonical_model_features (
                feature_id,security_id,feature_key,value,feature_as_of,available_at,
                source_phase,source_ref,quality_status,computation_version,evidence_json,created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(feature_id) DO UPDATE SET
                value=excluded.value,
                quality_status=excluded.quality_status,
                evidence_json=excluded.evidence_json,
                created_at=excluded.created_at
            """,
            (
                feature_id, security_id, feature_key, value, _iso(feature_as_of),
                _iso(available_at), source_phase, source_ref, quality_status,
                computation_version,
                json.dumps(evidence or {}, sort_keys=True, separators=(",", ":")),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self.store.connection.commit()
        return feature_id

    def load_as_of(self, security_id: str, as_of: datetime) -> dict[str, dict]:
        cutoff = _iso(as_of)
        rows = self.store.connection.execute(
            """
            WITH ranked AS (
                SELECT *,
                    ROW_NUMBER() OVER (
                        PARTITION BY feature_key
                        ORDER BY feature_as_of DESC, available_at DESC, created_at DESC
                    ) AS rn
                FROM canonical_model_features
                WHERE security_id=?
                  AND feature_as_of<=?
                  AND available_at<=?
                  AND source_phase IN (
                    'PHASE1_UNIVERSE','PHASE2_PRICE','PHASE3_FUNDAMENTAL',
                    'HISTORICAL_CONTROLS','DERIVED_CANONICAL'
                  )
            )
            SELECT * FROM ranked WHERE rn=1 ORDER BY feature_key
            """,
            (security_id, cutoff, cutoff),
        ).fetchall()
        return {row["feature_key"]: dict(row) for row in rows}

    def save_many(self, rows: Iterable[dict[str, Any]]) -> int:
        count = 0
        for row in rows:
            self.save_feature(**row)
            count += 1
        return count
