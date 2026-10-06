from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from core.contracts.enums import Exchange
from core.universe.models import UniverseRecord
from data.database.sqlite_store import SQLiteStore
from data.providers.stock_data_pit_universe import (
    StockDataPitUnavailable,
    StockDataPitUniverseProvider,
)
from data.repositories.security_repository import SecurityRepository


def _artifact(lines: list[dict]) -> tuple[dict, bytes]:
    blob = "".join(json.dumps(row, sort_keys=True) + "\n" for row in lines).encode("utf-8")
    manifest = {
        "reconstructable_from": "2026-07-28",
        "files": [
            {
                "name": "sec_company_tickers_exchange.jsonl",
                "sha256": hashlib.sha256(blob).hexdigest(),
            }
        ],
    }
    return manifest, blob


def test_public_pit_parser_enforces_floor_and_interval_membership() -> None:
    lines = [
        {
            "cik": 123,
            "ticker": "AAA",
            "title": "AAA Corp",
            "exchange": "Nasdaq",
            "valid_from": "2026-07-28",
            "valid_to": None,
            "provable_from": False,
        },
        {
            "cik": 456,
            "ticker": "OLD",
            "title": "Old Corp",
            "exchange": "NYSE",
            "valid_from": "2026-07-28",
            "valid_to": "2026-09-01",
            "provable_from": False,
        },
        {
            "cik": 789,
            "ticker": "AMX",
            "title": "American Corp",
            "exchange": "NYSE American",
            "valid_from": "2026-08-15",
            "valid_to": None,
            "provable_from": True,
        },
    ]
    manifest, blob = _artifact(lines)

    rows = StockDataPitUniverseProvider.parse(
        manifest=manifest,
        jsonl_bytes=blob,
        as_of=date(2026, 8, 20),
        availability_date=datetime(2026, 10, 7, tzinfo=timezone.utc),
    )
    assert {row.ticker for row in rows} == {"AAA", "OLD", "AMX"}
    assert {row.exchange for row in rows} == {
        Exchange.NASDAQ,
        Exchange.NYSE,
        Exchange.AMEX,
    }
    assert all(row.active is False for row in rows)

    rows_after = StockDataPitUniverseProvider.parse(
        manifest=manifest,
        jsonl_bytes=blob,
        as_of=date(2026, 9, 2),
        availability_date=datetime(2026, 10, 7, tzinfo=timezone.utc),
    )
    assert {row.ticker for row in rows_after} == {"AAA", "AMX"}

    with pytest.raises(StockDataPitUnavailable, match="begins 2026-07-28"):
        StockDataPitUniverseProvider.parse(
            manifest=manifest,
            jsonl_bytes=blob,
            as_of=date(2025, 10, 1),
        )


def test_public_pit_parser_rejects_tampered_artifact() -> None:
    manifest, blob = _artifact(
        [{
            "cik": 123,
            "ticker": "AAA",
            "title": "AAA Corp",
            "exchange": "Nasdaq",
            "valid_from": "2026-07-28",
            "valid_to": None,
            "provable_from": False,
        }]
    )
    with pytest.raises(StockDataPitUnavailable, match="SHA256 mismatch"):
        StockDataPitUniverseProvider.parse(
            manifest=manifest,
            jsonl_bytes=blob + b"tamper",
            as_of=date(2026, 8, 1),
        )


def test_historical_snapshot_does_not_flip_current_active_state(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "pit.sqlite")
    store.initialize()
    repo = SecurityRepository(store)
    try:
        now = datetime(2026, 10, 7, tzinfo=timezone.utc)
        repo.bulk_upsert(
            [
                UniverseRecord(
                    ticker="AAA",
                    name="AAA Corp",
                    exchange=Exchange.NASDAQ,
                    exchange_mic="XNAS",
                    active=True,
                    provider="SEC_EDGAR",
                    availability_date=now,
                    security_type="CS",
                    cik="0000000123",
                )
            ],
            snapshot_date=date(2026, 10, 7),
        )
        repo.bulk_upsert_historical_snapshot(
            [
                UniverseRecord(
                    ticker="AAA",
                    name="AAA Corp",
                    exchange=Exchange.NASDAQ,
                    exchange_mic="XNAS",
                    active=False,
                    provider="STOCK_DATA_PIT",
                    availability_date=now,
                    cik="0000000123",
                ),
                UniverseRecord(
                    ticker="OLD",
                    name="Old Corp",
                    exchange=Exchange.NYSE,
                    exchange_mic="XNYS",
                    active=False,
                    provider="STOCK_DATA_PIT",
                    availability_date=now,
                    cik="0000000456",
                ),
            ],
            snapshot_date=date(2026, 8, 20),
        )

        current = store.connection.execute(
            "SELECT active FROM security_master WHERE ticker='AAA'"
        ).fetchone()
        old = store.connection.execute(
            "SELECT active FROM security_master WHERE ticker='OLD'"
        ).fetchone()
        assert current["active"] == 1
        assert old["active"] == 0

        snapshot = repo.universe_as_of(date(2026, 8, 20))
        assert {row["ticker"] for row in snapshot} == {"AAA", "OLD"}
    finally:
        store.close()
