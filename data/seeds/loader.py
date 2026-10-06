from __future__ import annotations

import csv
from datetime import date, datetime, timezone
from pathlib import Path

from core.contracts.enums import Exchange
from core.universe.global_models import GlobalReferenceListing
from core.universe.models import UniverseRecord
from data.database.sqlite_store import SQLiteStore
from data.repositories.global_security_repository import GlobalSecurityRepository
from data.repositories.security_repository import SecurityRepository


def bundled_sec_seed_path() -> Path:
    return Path(__file__).with_name("sec_us_current.csv")


def bundled_jp_tr_hk_seed_path() -> Path:
    return Path(__file__).with_name("jp_tr_hk_current.csv")


def bootstrap_bundled_us_seed(store: SQLiteStore) -> int:
    """Load the bundled SEC US universe when a fresh runtime DB is empty.

    The installer build generates sec_us_current.csv from SEC EDGAR. Source-tree
    development is allowed to omit the generated CSV.
    """

    path = bundled_sec_seed_path()
    if not path.exists():
        return 0

    repo = SecurityRepository(store)
    existing = store.connection.execute(
        """
        SELECT COUNT(*) AS n
        FROM security_master
        WHERE market='US'
        """
    ).fetchone()
    if existing is not None and int(existing["n"]) >= 1000:
        return 0

    records: list[UniverseRecord] = []
    snapshot_date: date | None = None
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "snapshot_date",
            "ticker",
            "name",
            "exchange",
            "exchange_mic",
            "cik",
        }
        if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
            raise RuntimeError(f"Unexpected bundled SEC seed columns: {reader.fieldnames}")

        for row in reader:
            ticker = (row.get("ticker") or "").strip().upper()
            name = (row.get("name") or "").strip()
            exchange_text = (row.get("exchange") or "").strip().upper()
            if not ticker or not name or not exchange_text:
                continue
            try:
                exchange = Exchange(exchange_text)
            except ValueError:
                continue

            row_date = date.fromisoformat(row["snapshot_date"])
            snapshot_date = snapshot_date or row_date
            availability = datetime.combine(
                row_date,
                datetime.min.time(),
                tzinfo=timezone.utc,
            )
            records.append(
                UniverseRecord(
                    ticker=ticker,
                    name=name,
                    exchange=exchange,
                    exchange_mic=(row.get("exchange_mic") or "").strip(),
                    active=True,
                    provider="SEC_EDGAR",
                    availability_date=availability,
                    security_type=None,
                    cik=(row.get("cik") or "").strip() or None,
                    currency="USD",
                    locale="us",
                )
            )

    if not records:
        return 0

    repo.bulk_upsert(records, snapshot_date=snapshot_date)
    return len(records)


def bootstrap_bundled_jp_tr_hk_seed(store: SQLiteStore) -> int:
    """Load packaged Japan/Turkey/Hong Kong reference listings.

    These rows are intentionally REFERENCE_ONLY. They make symbol discovery and
    offline startup broad and reliable, but they are not automatically promoted
    to canonical S15.3 evidence.
    """

    path = bundled_jp_tr_hk_seed_path()
    if not path.exists():
        return 0

    existing = store.connection.execute(
        """
        SELECT COUNT(*) AS n
        FROM security_master
        WHERE market IN ('JP','TR','HK')
        """
    ).fetchone()
    if existing is not None and int(existing["n"]) >= 4000:
        return 0

    records: list[GlobalReferenceListing] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "market",
            "exchange",
            "mic",
            "ticker",
            "source_symbol",
            "name",
            "asset_type",
            "country",
            "country_code",
            "source",
            "source_scope",
            "redistribution_status",
        }
        if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
            raise RuntimeError(
                f"Unexpected bundled JP/TR/HK seed columns: {reader.fieldnames}"
            )

        for row in reader:
            market = (row.get("market") or "").strip().upper()
            exchange = (row.get("exchange") or "").strip().upper()
            ticker = (row.get("ticker") or "").strip().upper()
            source_symbol = (row.get("source_symbol") or "").strip().upper()
            name = (row.get("name") or "").strip()
            if market not in {"JP", "TR", "HK"} or not exchange or not ticker or not name:
                continue

            records.append(
                GlobalReferenceListing(
                    listing_key=f"{exchange}::{ticker}",
                    ticker=ticker,
                    exchange=exchange,
                    name=name,
                    asset_type=(row.get("asset_type") or "").strip() or None,
                    country=(row.get("country") or "").strip() or None,
                    country_code=(row.get("country_code") or "").strip().upper() or None,
                    isin=(row.get("isin") or "").strip().upper() or None,
                    aliases=source_symbol or None,
                    currency=(row.get("currency") or "").strip().upper() or None,
                    mic=(row.get("mic") or "").strip().upper() or None,
                    sector=(row.get("sector") or "").strip() or None,
                    industry=(row.get("industry") or "").strip() or None,
                    figi=(row.get("figi") or "").strip().upper() or None,
                    composite_figi=(
                        (row.get("composite_figi") or "").strip().upper() or None
                    ),
                    shareclass_figi=(
                        (row.get("shareclass_figi") or "").strip().upper() or None
                    ),
                    market_code=market,
                    active=True,
                    source=(row.get("source") or "FINANCEDATABASE_MIT_REFERENCE").strip(),
                    source_scope=(row.get("source_scope") or "REFERENCE_ONLY").strip(),
                    redistribution_status=(
                        row.get("redistribution_status")
                        or "MIT_REFERENCE_REQUIRES_SOURCE_POLICY"
                    ).strip(),
                )
            )

    if not records:
        return 0

    return GlobalSecurityRepository(store).bulk_upsert_reference(records)
