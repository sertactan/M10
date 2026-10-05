from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Iterable

from core.universe.identity import stable_security_id
from core.universe.models import TickerChangeEvent, UniverseRecord
from data.database.sqlite_store import SQLiteStore


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return dt.astimezone(timezone.utc).isoformat()


class SecurityRepository:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def upsert_record(self, record: UniverseRecord, *, snapshot_date: date | None = None) -> str:
        security_id = self._resolve_existing_security_id(record) or stable_security_id(record)
        now = datetime.now(timezone.utc).isoformat()
        self.store.connection.execute(
            """
            INSERT INTO security_master (
                security_id,ticker,name,exchange,market,cik,sector,industry,ipo_date,delisted_date,
                active,created_at,updated_at,primary_exchange_mic,security_type,currency,locale,
                composite_figi,share_class_figi,source_priority,first_seen,last_seen
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(security_id) DO UPDATE SET
                ticker=excluded.ticker,
                name=CASE WHEN excluded.name<>'' THEN excluded.name ELSE security_master.name END,
                exchange=excluded.exchange,
                cik=COALESCE(excluded.cik,security_master.cik),
                ipo_date=COALESCE(excluded.ipo_date,security_master.ipo_date),
                delisted_date=COALESCE(excluded.delisted_date,security_master.delisted_date),
                active=excluded.active,
                updated_at=excluded.updated_at,
                primary_exchange_mic=COALESCE(excluded.primary_exchange_mic,security_master.primary_exchange_mic),
                security_type=COALESCE(excluded.security_type,security_master.security_type),
                currency=COALESCE(excluded.currency,security_master.currency),
                locale=COALESCE(excluded.locale,security_master.locale),
                composite_figi=COALESCE(excluded.composite_figi,security_master.composite_figi),
                share_class_figi=COALESCE(excluded.share_class_figi,security_master.share_class_figi),
                source_priority=MIN(security_master.source_priority,excluded.source_priority),
                first_seen=MIN(COALESCE(security_master.first_seen,excluded.first_seen),excluded.first_seen),
                last_seen=MAX(COALESCE(security_master.last_seen,excluded.last_seen),excluded.last_seen)
            """,
            (
                security_id,
                record.ticker,
                record.name,
                record.exchange.value,
                "US",
                record.cik,
                None,
                None,
                record.ipo_date.isoformat() if record.ipo_date else None,
                record.delisted_date.isoformat() if record.delisted_date else None,
                1 if record.active else 0,
                now,
                now,
                record.exchange_mic,
                record.security_type,
                record.currency,
                record.locale,
                record.composite_figi,
                record.share_class_figi,
                self._source_priority(record.provider),
                record.availability_date.date().isoformat(),
                record.availability_date.date().isoformat(),
            ),
        )
        self._upsert_alias(
            security_id=security_id,
            ticker=record.ticker,
            valid_from=record.ipo_date,
            valid_to=record.delisted_date,
            source=record.provider,
            event_type="listing",
            availability_date=record.availability_date,
        )
        if snapshot_date is not None and record.active:
            self.store.connection.execute(
                """
                INSERT INTO universe_snapshot_membership (
                    snapshot_date,security_id,ticker,exchange,exchange_mic,security_type,
                    source,availability_date,ingested_at
                ) VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(snapshot_date,security_id,ticker,source) DO UPDATE SET
                    exchange=excluded.exchange,
                    exchange_mic=excluded.exchange_mic,
                    security_type=COALESCE(excluded.security_type,universe_snapshot_membership.security_type),
                    availability_date=excluded.availability_date,
                    ingested_at=excluded.ingested_at
                """,
                (
                    snapshot_date.isoformat(),
                    security_id,
                    record.ticker,
                    record.exchange.value,
                    record.exchange_mic,
                    record.security_type,
                    record.provider,
                    _iso(record.availability_date),
                    now,
                ),
            )
        return security_id

    def _resolve_existing_security_id(self, record: UniverseRecord) -> str | None:
        if record.share_class_figi:
            row = self.store.connection.execute(
                "SELECT security_id FROM security_master WHERE share_class_figi=? LIMIT 1",
                (record.share_class_figi,),
            ).fetchone()
            if row:
                return row["security_id"]
        if record.composite_figi:
            row = self.store.connection.execute(
                "SELECT security_id FROM security_master WHERE composite_figi=? LIMIT 1",
                (record.composite_figi,),
            ).fetchone()
            if row:
                return row["security_id"]
        if record.cik:
            row = self.store.connection.execute(
                """
                SELECT security_id FROM security_master
                WHERE cik=? AND ticker=? AND exchange=?
                ORDER BY active DESC LIMIT 1
                """,
                (record.cik, record.ticker, record.exchange.value),
            ).fetchone()
            if row:
                return row["security_id"]
        row = self.store.connection.execute(
            """
            SELECT security_id FROM security_master
            WHERE ticker=? AND exchange=?
            ORDER BY active DESC, updated_at DESC LIMIT 1
            """,
            (record.ticker, record.exchange.value),
        ).fetchone()
        return row["security_id"] if row else None

    def bulk_upsert(self, records: Iterable[UniverseRecord], *, snapshot_date: date | None = None) -> int:
        count = 0
        for record in records:
            self.upsert_record(record, snapshot_date=snapshot_date)
            count += 1
        self.store.connection.commit()
        return count

    def merge_sec_identity(self, record: UniverseRecord) -> str | None:
        row = self.store.connection.execute(
            """
            SELECT security_id FROM security_master
            WHERE ticker=? AND exchange=?
            ORDER BY active DESC, updated_at DESC
            LIMIT 1
            """,
            (record.ticker, record.exchange.value),
        ).fetchone()
        if row is None:
            return self.upsert_record(record)
        security_id = row["security_id"]
        self.store.connection.execute(
            """
            UPDATE security_master
            SET cik=COALESCE(?,cik), name=CASE WHEN ?<>'' THEN ? ELSE name END,
                updated_at=?, source_priority=MIN(source_priority,?)
            WHERE security_id=?
            """,
            (
                record.cik,
                record.name,
                record.name,
                datetime.now(timezone.utc).isoformat(),
                self._source_priority(record.provider),
                security_id,
            ),
        )
        self.store.connection.commit()
        return security_id

    def apply_ticker_events(self, security_id: str, events: list[TickerChangeEvent]) -> None:
        if not events:
            return
        ordered = sorted(events, key=lambda e: e.event_date)
        for idx, event in enumerate(ordered):
            valid_to = None
            if idx + 1 < len(ordered):
                valid_to = date.fromordinal(ordered[idx + 1].event_date.toordinal() - 1)
            self._upsert_alias(
                security_id=security_id,
                ticker=event.ticker,
                valid_from=event.event_date,
                valid_to=valid_to,
                source=event.provider,
                event_type=event.event_type,
                availability_date=event.availability_date,
            )
        latest = ordered[-1]
        self.store.connection.execute(
            "UPDATE security_master SET ticker=?, updated_at=? WHERE security_id=?",
            (latest.ticker, datetime.now(timezone.utc).isoformat(), security_id),
        )
        self.store.connection.commit()

    def universe_as_of(self, snapshot_date: date) -> list[dict]:
        rows = self.store.connection.execute(
            """
            SELECT sm.*, usm.snapshot_date, usm.source AS snapshot_source
            FROM universe_snapshot_membership usm
            JOIN security_master sm ON sm.security_id=usm.security_id
            WHERE usm.snapshot_date=?
              AND usm.exchange IN ('NASDAQ','NYSE','AMEX')
            ORDER BY usm.ticker
            """,
            (snapshot_date.isoformat(),),
        ).fetchall()
        return [dict(row) for row in rows]

    def current_us_common_stocks(self) -> list[dict]:
        rows = self.store.connection.execute(
            """
            SELECT * FROM security_master
            WHERE active=1
              AND exchange IN ('NASDAQ','NYSE','AMEX')
              AND (security_type='CS' OR security_type IS NULL)
            ORDER BY ticker
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def lookup_security_id(self, *, ticker: str, exchange: str | None = None) -> str | None:
        if exchange:
            row = self.store.connection.execute(
                "SELECT security_id FROM security_master WHERE ticker=? AND exchange=? ORDER BY active DESC LIMIT 1",
                (ticker.upper(), exchange),
            ).fetchone()
        else:
            row = self.store.connection.execute(
                "SELECT security_id FROM security_master WHERE ticker=? ORDER BY active DESC LIMIT 1",
                (ticker.upper(),),
            ).fetchone()
        return row["security_id"] if row else None

    def _upsert_alias(
        self,
        *,
        security_id: str,
        ticker: str,
        valid_from: date | None,
        valid_to: date | None,
        source: str,
        event_type: str,
        availability_date: datetime,
    ) -> None:
        self.store.connection.execute(
            """
            INSERT INTO ticker_aliases (
                alias,security_id,valid_from,valid_to,source,event_type,availability_date,ingested_at
            ) VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(alias,security_id,valid_from) DO UPDATE SET
                valid_to=COALESCE(excluded.valid_to,ticker_aliases.valid_to),
                source=excluded.source,
                event_type=excluded.event_type,
                availability_date=excluded.availability_date,
                ingested_at=excluded.ingested_at
            """,
            (
                ticker.upper(),
                security_id,
                valid_from.isoformat() if valid_from else "",
                valid_to.isoformat() if valid_to else None,
                source,
                event_type,
                _iso(availability_date),
                datetime.now(timezone.utc).isoformat(),
            ),
        )

    @staticmethod
    def _source_priority(provider: str) -> int:
        return {"SEC_EDGAR": 1, "MASSIVE": 2, "FINNHUB": 3, "FMP": 4}.get(provider, 99)
