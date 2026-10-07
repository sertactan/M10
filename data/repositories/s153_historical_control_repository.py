from __future__ import annotations

import json
from datetime import datetime, timezone

from data.database.sqlite_store import SQLiteStore


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return dt.astimezone(timezone.utc).isoformat()


class S153HistoricalControlRepository:
    def __init__(self, store: SQLiteStore) -> None:
        self.store=store

    def save(
        self,
        *,
        observation_id: str,
        security_id: str,
        as_of_date: str,
        primary_route: str | None,
        feature_vector: dict,
        magnitude_vector: dict,
        fm252: float,
        outcome_class: str,
        label_available_at: datetime,
        vector_version: str,
        source_run_id: str | None = None,
    ) -> None:
        self.store.connection.execute(
            """
            INSERT INTO s153_historical_control_observations (
                observation_id,security_id,as_of_date,primary_route,
                feature_vector_json,magnitude_vector_json,fm252,outcome_class,
                label_available_at,source_run_id,vector_version,created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(observation_id) DO UPDATE SET
                feature_vector_json=excluded.feature_vector_json,
                magnitude_vector_json=excluded.magnitude_vector_json,
                fm252=excluded.fm252,
                outcome_class=excluded.outcome_class,
                label_available_at=excluded.label_available_at,
                vector_version=excluded.vector_version,
                created_at=excluded.created_at
            """,
            (
                observation_id,security_id,as_of_date,primary_route,
                json.dumps(feature_vector,sort_keys=True,separators=(",",":")),
                json.dumps(magnitude_vector,sort_keys=True,separators=(",",":")),
                float(fm252),outcome_class,_iso(label_available_at),source_run_id,
                vector_version,datetime.now(timezone.utc).isoformat(),
            ),
        )
        self.store.connection.commit()

    def eligible_before(self, as_of: datetime, *, vector_version: str) -> list[dict]:
        rows=self.store.connection.execute(
            """
            SELECT *
            FROM s153_historical_control_observations
            WHERE label_available_at<=?
              AND vector_version=?
            ORDER BY as_of_date,security_id,observation_id
            """,
            (_iso(as_of),vector_version),
        ).fetchall()
        out=[]
        for row in rows:
            item=dict(row)
            item["feature_vector"]=json.loads(item.pop("feature_vector_json"))
            item["magnitude_vector"]=json.loads(item.pop("magnitude_vector_json"))
            out.append(item)
        return out
