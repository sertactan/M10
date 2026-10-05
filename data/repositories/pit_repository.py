from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from data.database.sqlite_store import SQLiteStore


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        raise ValueError("PIT timestamp must be timezone-aware")
    return dt.astimezone(timezone.utc).isoformat()


class PITRepository:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def financial_facts_as_of(self, security_id: str, as_of: datetime) -> list[dict[str, Any]]:
        rows = self.store.connection.execute(
            """
            WITH ranked AS (
                SELECT *,
                       ROW_NUMBER() OVER (
                           PARTITION BY security_id, fact_key, COALESCE(period_date, '')
                           ORDER BY availability_date DESC, ingested_at DESC
                       ) AS rn
                FROM financial_facts
                WHERE security_id = ?
                  AND availability_date <= ?
            )
            SELECT * FROM ranked
            WHERE rn = 1
            ORDER BY fact_key, period_date
            """,
            (security_id, _iso(as_of)),
        ).fetchall()
        return [dict(row) for row in rows]

    def prices_as_of(
        self, security_id: str, as_of: datetime, start_date: str | None = None
    ) -> list[dict[str, Any]]:
        params: list[Any] = [security_id, as_of.date().isoformat(), _iso(as_of)]
        extra = ""
        if start_date:
            extra = " AND trade_date >= ?"
            params.append(start_date)
        rows = self.store.connection.execute(
            f"""
            WITH ranked AS (
                SELECT *,
                       ROW_NUMBER() OVER (
                           PARTITION BY security_id, trade_date
                           ORDER BY availability_date DESC, ingested_at DESC
                       ) AS rn
                FROM price_daily
                WHERE security_id = ?
                  AND trade_date <= ?
                  AND availability_date <= ?
                  {extra}
            )
            SELECT * FROM ranked
            WHERE rn = 1
            ORDER BY trade_date
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]

    def save_analysis_run(self, payload: dict[str, Any]) -> None:
        required = {
            "analysis_id", "ticker", "security_id", "analysis_date", "mode",
            "model_version", "data_snapshot_hash", "model_config_hash", "status", "created_at"
        }
        missing = required.difference(payload)
        if missing:
            raise ValueError(f"Missing analysis fields: {sorted(missing)}")
        columns = [
            "analysis_id", "ticker", "security_id", "analysis_date", "mode",
            "model_version", "data_snapshot_hash", "model_config_hash", "score", "route",
            "destination", "prediction", "status", "created_at"
        ]
        values = [payload.get(c) for c in columns]
        marks = ",".join("?" for _ in columns)
        self.store.connection.execute(
            f"INSERT INTO analysis_runs ({','.join(columns)}) VALUES ({marks})", values
        )
        self.store.connection.commit()

    @staticmethod
    def stable_json(data: Any) -> str:
        return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
