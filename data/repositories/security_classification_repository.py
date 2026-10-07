from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from data.database.sqlite_store import SQLiteStore


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return dt.astimezone(timezone.utc).isoformat()


class SecurityClassificationRepository:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def save(
        self,
        *,
        security_id: str,
        sector: str,
        industry: str,
        effective_from: date,
        effective_to: date | None,
        available_at: datetime,
        source: str,
        source_document: str | None = None,
        quality_status: str = "PIT_CANONICAL",
    ) -> str:
        if not sector.strip() or not industry.strip():
            raise ValueError("sector and industry are required")
        identity="|".join([
            security_id,sector.strip(),industry.strip(),
            effective_from.isoformat(),
            effective_to.isoformat() if effective_to else "",
            _iso(available_at),source,
        ])
        cid=str(uuid.uuid5(uuid.NAMESPACE_URL,identity))
        self.store.connection.execute(
            """
            INSERT INTO security_classification_history (
                classification_id,security_id,sector,industry,effective_from,
                effective_to,available_at,source,source_document,quality_status,created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(classification_id) DO UPDATE SET
                source_document=excluded.source_document,
                quality_status=excluded.quality_status,
                created_at=excluded.created_at
            """,
            (
                cid,security_id,sector.strip(),industry.strip(),
                effective_from.isoformat(),
                effective_to.isoformat() if effective_to else None,
                _iso(available_at),source,source_document,quality_status,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self.store.connection.commit()
        return cid

    def as_of(self, security_id: str, as_of: datetime) -> dict | None:
        if as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")
        d=as_of.date().isoformat()
        row=self.store.connection.execute(
            """
            SELECT *
            FROM security_classification_history
            WHERE security_id=?
              AND effective_from<=?
              AND (effective_to IS NULL OR effective_to>=?)
              AND available_at<=?
            ORDER BY effective_from DESC,available_at DESC,created_at DESC
            LIMIT 1
            """,
            (security_id,d,d,_iso(as_of)),
        ).fetchone()
        return dict(row) if row is not None else None
