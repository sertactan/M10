from __future__ import annotations

import csv
from datetime import date, datetime, timezone
from pathlib import Path

from core.contracts.enums import Exchange
from core.universe.models import UniverseRecord
from data.database.sqlite_store import SQLiteStore
from data.repositories.security_repository import SecurityRepository


def bundled_sec_seed_path() -> Path:
    return Path(__file__).with_name("sec_us_current.csv")


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
