from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Iterable

from core.universe.global_models import GlobalReferenceListing
from data.database.sqlite_store import SQLiteStore


class GlobalSecurityRepository:
    """Import broad reference listings without weakening canonical source rules."""

    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def upsert_reference(self, record: GlobalReferenceListing) -> str:
        now = datetime.now(timezone.utc).isoformat()
        existing = self.store.connection.execute(
            """
            SELECT *
            FROM security_master
            WHERE listing_key=?
               OR (ticker=? AND exchange=?)
            ORDER BY
                CASE WHEN source_scope='CANONICAL' THEN 0 ELSE 1 END,
                active DESC,
                updated_at DESC
            LIMIT 1
            """,
            (record.listing_key, record.ticker, record.exchange),
        ).fetchone()

        if existing is not None:
            security_id = str(existing["security_id"])
            existing_scope = str(existing["source_scope"] or "CANONICAL")
            self.store.connection.execute(
                """
                UPDATE security_master
                SET listing_key=COALESCE(listing_key,?),
                    country=COALESCE(country,?),
                    country_code=COALESCE(country_code,?),
                    isin=COALESCE(isin,?),
                    asset_type=COALESCE(asset_type,?),
                    aliases=COALESCE(aliases,?),
                    market=CASE
                        WHEN market IS NULL OR market='' OR market='US'
                        THEN COALESCE(NULLIF(?,''),market)
                        ELSE market
                    END,
                    source_scope=?,
                    redistribution_status=COALESCE(redistribution_status,?),
                    updated_at=?
                WHERE security_id=?
                """,
                (
                    record.listing_key,
                    record.country,
                    record.country_code,
                    record.isin,
                    record.asset_type,
                    record.aliases,
                    record.market,
                    existing_scope,
                    record.redistribution_status,
                    now,
                    security_id,
                ),
            )
            return security_id

        security_id = "SEC_" + uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"GLOBAL_REFERENCE|{record.listing_key}",
        ).hex.upper()
        self.store.connection.execute(
            """
            INSERT INTO security_master (
                security_id,ticker,name,exchange,market,cik,sector,industry,
                ipo_date,delisted_date,active,created_at,updated_at,
                primary_exchange_mic,security_type,currency,locale,
                composite_figi,share_class_figi,listing_key,country,country_code,
                isin,asset_type,aliases,source_scope,redistribution_status,
                source_priority,first_seen,last_seen
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                security_id,
                record.ticker,
                record.name,
                record.exchange,
                record.market,
                None,
                None,
                None,
                None,
                None,
                1,
                now,
                now,
                None,
                record.asset_type,
                None,
                (record.country_code or "").lower() or None,
                None,
                None,
                record.listing_key,
                record.country,
                record.country_code,
                record.isin,
                record.asset_type,
                record.aliases,
                record.source_scope,
                record.redistribution_status,
                90,
                None,
                None,
            ),
        )
        return security_id

    def bulk_upsert_reference(
        self,
        records: Iterable[GlobalReferenceListing],
    ) -> int:
        count = 0
        for record in records:
            self.upsert_reference(record)
            count += 1
        self.store.connection.commit()
        return count

    def count_by_market(self) -> dict[str, int]:
        rows = self.store.connection.execute(
            """
            SELECT market,COUNT(*) AS n
            FROM security_master
            WHERE active=1
            GROUP BY market
            ORDER BY n DESC, market
            """
        ).fetchall()
        return {str(row["market"]): int(row["n"]) for row in rows}

    def current_market(
        self,
        market: str,
        *,
        asset_type: str | None = None,
    ) -> list[dict]:
        params: list[object] = [market.upper()]
        predicate = ""
        if asset_type is not None:
            predicate = " AND asset_type=?"
            params.append(asset_type)
        rows = self.store.connection.execute(
            f"""
            SELECT *
            FROM security_master
            WHERE active=1 AND UPPER(market)=? {predicate}
            ORDER BY exchange,ticker
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]
