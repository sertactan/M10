from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable

from core.historical.s16_evidence import (
    S16AttentionRecord,
    S16FeatureEvidenceRecord,
    S16ShortInterestRecord,
)
from data.database.sqlite_store import SQLiteStore


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat()


class S16EvidenceRepository:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def save_short_interest(
        self,
        record: S16ShortInterestRecord,
        *,
        raw: dict[str, Any] | None = None,
    ) -> str:
        if record.available_at.date() < record.settlement_date:
            raise ValueError("short-interest available_at cannot predate settlement_date")
        identity = "|".join([
            "S16_SHORT",
            record.security_id,
            record.source,
            record.settlement_date.isoformat(),
            record.source_ref,
        ])
        record_id = str(uuid.uuid5(uuid.NAMESPACE_URL, identity))
        self.store.connection.execute(
            """
            INSERT INTO s16_short_interest_source (
                record_id,security_id,ticker,settlement_date,short_interest,
                avg_daily_volume,float_shares,days_to_cover,available_at,
                source,source_ref,quality_status,raw_json,created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(record_id) DO UPDATE SET
                short_interest=excluded.short_interest,
                avg_daily_volume=excluded.avg_daily_volume,
                float_shares=excluded.float_shares,
                days_to_cover=excluded.days_to_cover,
                available_at=excluded.available_at,
                quality_status=excluded.quality_status,
                raw_json=excluded.raw_json,
                created_at=excluded.created_at
            """,
            (
                record_id, record.security_id, record.ticker.upper(),
                record.settlement_date.isoformat(), float(record.short_interest),
                record.avg_daily_volume, record.float_shares, record.days_to_cover,
                _iso(record.available_at), record.source, record.source_ref,
                record.quality_status,
                json.dumps(raw or {}, sort_keys=True, separators=(",", ":")),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self.store.connection.commit()
        return record_id

    def save_attention(
        self,
        record: S16AttentionRecord,
        *,
        raw: dict[str, Any] | None = None,
    ) -> str:
        if record.available_at < record.observed_at:
            raise ValueError("attention available_at cannot predate observed_at")
        channel = record.channel.upper()
        if channel not in {"NEWS", "SOCIAL", "SEARCH"}:
            raise ValueError(f"unsupported S16 attention channel: {record.channel}")
        identity = "|".join([
            "S16_ATTENTION",
            record.security_id,
            channel,
            record.source,
            _iso(record.observed_at),
            record.source_ref,
        ])
        record_id = str(uuid.uuid5(uuid.NAMESPACE_URL, identity))
        self.store.connection.execute(
            """
            INSERT INTO s16_attention_source (
                record_id,security_id,ticker,channel,observed_at,available_at,
                mentions,unique_authors,sentiment,source,source_ref,quality_status,
                raw_json,created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(record_id) DO UPDATE SET
                mentions=excluded.mentions,
                unique_authors=excluded.unique_authors,
                sentiment=excluded.sentiment,
                available_at=excluded.available_at,
                quality_status=excluded.quality_status,
                raw_json=excluded.raw_json,
                created_at=excluded.created_at
            """,
            (
                record_id, record.security_id, record.ticker.upper(), channel,
                _iso(record.observed_at), _iso(record.available_at),
                float(record.mentions), record.unique_authors, record.sentiment,
                record.source, record.source_ref, record.quality_status,
                json.dumps(raw or {}, sort_keys=True, separators=(",", ":")),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self.store.connection.commit()
        return record_id

    def save_feature_evidence(
        self,
        record: S16FeatureEvidenceRecord,
        *,
        raw: dict[str, Any] | None = None,
    ) -> str:
        if record.available_at < record.observed_at:
            raise ValueError("feature evidence available_at cannot predate observed_at")
        identity = "|".join([
            "S16_FEATURE",
            record.security_id,
            record.feature_key,
            record.source,
            _iso(record.observed_at),
            record.source_ref,
        ])
        record_id = str(uuid.uuid5(uuid.NAMESPACE_URL, identity))
        self.store.connection.execute(
            """
            INSERT INTO s16_feature_evidence_source (
                record_id,security_id,ticker,feature_key,observed_at,available_at,
                value,source,source_ref,quality_status,raw_json,created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(record_id) DO UPDATE SET
                value=excluded.value,
                available_at=excluded.available_at,
                quality_status=excluded.quality_status,
                raw_json=excluded.raw_json,
                created_at=excluded.created_at
            """,
            (
                record_id, record.security_id, record.ticker.upper(),
                record.feature_key, _iso(record.observed_at),
                _iso(record.available_at), float(record.value),
                record.source, record.source_ref, record.quality_status,
                json.dumps(raw or {}, sort_keys=True, separators=(",", ":")),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self.store.connection.commit()
        return record_id

    def latest_short_interest_as_of(
        self, security_id: str, as_of: datetime
    ) -> dict | None:
        cutoff = _iso(as_of)
        row = self.store.connection.execute(
            """
            SELECT *
            FROM s16_short_interest_source
            WHERE security_id=?
              AND available_at<=?
            ORDER BY settlement_date DESC,available_at DESC,created_at DESC
            LIMIT 1
            """,
            (security_id, cutoff),
        ).fetchone()
        return dict(row) if row is not None else None

    def attention_as_of(
        self,
        security_id: str,
        channel: str,
        as_of: datetime,
        *,
        limit: int = 500,
    ) -> list[dict]:
        cutoff = _iso(as_of)
        rows = self.store.connection.execute(
            """
            SELECT *
            FROM s16_attention_source
            WHERE security_id=? AND channel=? AND available_at<=? AND observed_at<=?
            ORDER BY observed_at DESC
            LIMIT ?
            """,
            (security_id, channel.upper(), cutoff, cutoff, int(limit)),
        ).fetchall()
        return [dict(row) for row in rows]

    def latest_feature_evidence_as_of(
        self,
        security_id: str,
        feature_key: str,
        as_of: datetime,
    ) -> dict | None:
        cutoff = _iso(as_of)
        row = self.store.connection.execute(
            """
            SELECT *
            FROM s16_feature_evidence_source
            WHERE security_id=? AND feature_key=?
              AND observed_at<=? AND available_at<=?
            ORDER BY observed_at DESC,available_at DESC,created_at DESC
            LIMIT 1
            """,
            (security_id, feature_key, cutoff, cutoff),
        ).fetchone()
        return dict(row) if row is not None else None

    def save_short_many(self, rows: Iterable[S16ShortInterestRecord]) -> int:
        return sum(1 for row in rows if self.save_short_interest(row))

    def save_attention_many(self, rows: Iterable[S16AttentionRecord]) -> int:
        return sum(1 for row in rows if self.save_attention(row))

    def save_feature_many(self, rows: Iterable[S16FeatureEvidenceRecord]) -> int:
        return sum(1 for row in rows if self.save_feature_evidence(row))
