from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from core.contracts.enums import Exchange
from core.universe.identity import exchange_from_mic, normalize_cik, stable_security_id
from core.universe.models import TickerChangeEvent, UniverseRecord
from core.universe.service import USUniverseService
from data.database.sqlite_store import SQLiteStore
from data.providers.finnhub_universe import FinnhubUniverseProvider
from data.providers.massive_universe import MassiveUniverseProvider
from data.providers.sec_edgar_universe import SECEdgarUniverseProvider
from data.repositories.security_repository import SecurityRepository


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)


def test_sec_parser_maps_target_exchanges() -> None:
    payload = {
        "fields": ["cik", "name", "ticker", "exchange"],
        "data": [
            [320193, "Apple Inc.", "AAPL", "Nasdaq"],
            [789019, "Microsoft Corp", "MSFT", "Nasdaq"],
            [1067983, "Berkshire", "BRK-B", "NYSE"],
            [12345, "American Co", "ABC", "NYSE American"],
            [999, "OTC Co", "OTC", "OTC"],
            [1000, "CBOE Fund", "CBF", "CBOE"],
        ],
    }
    rows = SECEdgarUniverseProvider.parse_ticker_exchange_payload(payload, availability_date=NOW)
    assert [r.ticker for r in rows] == ["AAPL", "MSFT", "BRK-B", "ABC", "OTC", "CBF"]
    assert rows[3].exchange is Exchange.AMEX
    assert rows[4].exchange is Exchange.OTC
    assert rows[5].exchange is Exchange.CBOE
    assert rows[0].cik == "0000320193"


def test_massive_parser_keeps_only_target_primary_exchanges_and_delisted() -> None:
    payload = {
        "results": [
            {
                "ticker": "AAPL", "name": "Apple Inc.", "market": "stocks", "locale": "us",
                "primary_exchange": "XNAS", "type": "CS", "active": True,
                "cik": "320193", "composite_figi": "BBG000B9XRY4", "share_class_figi": "BBG001S5N8V8",
                "currency_symbol": "usd",
            },
            {
                "ticker": "OLD", "name": "Old Corp", "primary_exchange": "XNYS", "type": "CS",
                "active": False, "delisted_utc": "2024-01-12T00:00:00Z",
            },
            {
                "ticker": "ETF", "name": "ETF", "primary_exchange": "ARCX", "type": "ETF", "active": True,
            },
        ]
    }
    rows = MassiveUniverseProvider.parse_tickers_payload(payload, availability_date=NOW)
    assert [r.ticker for r in rows] == ["AAPL", "OLD"]
    assert rows[1].active is False
    assert rows[1].delisted_date == date(2024, 1, 12)
    assert rows[0].share_class_figi == "BBG001S5N8V8"


def test_stable_security_id_survives_ticker_change_when_figi_same() -> None:
    base = dict(
        name="Meta Platforms, Inc.", exchange=Exchange.NASDAQ, exchange_mic="XNAS",
        active=True, provider="MASSIVE", availability_date=NOW, security_type="CS",
        cik="0001326801", composite_figi="BBG000MM2P62", share_class_figi="BBG001SQCQC5",
    )
    assert stable_security_id(UniverseRecord(ticker="FB", **base)) == stable_security_id(
        UniverseRecord(ticker="META", **base)
    )


def test_repository_snapshot_and_alias_history(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "op.db")
    store.initialize(ROOT / "data" / "database" / "schema.sql")
    repo = SecurityRepository(store)
    record = UniverseRecord(
        ticker="META", name="Meta Platforms, Inc.", exchange=Exchange.NASDAQ,
        exchange_mic="XNAS", active=True, provider="MASSIVE", availability_date=NOW,
        security_type="CS", cik="0001326801", composite_figi="BBG000MM2P62",
        share_class_figi="BBG001SQCQC5",
    )
    sid = repo.upsert_record(record, snapshot_date=date(2026, 10, 5))
    repo.apply_ticker_events(sid, [
        TickerChangeEvent(date(2012, 5, 18), "FB", "MASSIVE", NOW),
        TickerChangeEvent(date(2022, 6, 9), "META", "MASSIVE", NOW),
    ])
    rows = repo.universe_as_of(date(2026, 10, 5))
    aliases = store.connection.execute(
        "SELECT alias,valid_from,valid_to FROM ticker_aliases WHERE security_id=? ORDER BY valid_from",
        (sid,),
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["ticker"] == "META"
    assert [(a["alias"], a["valid_from"]) for a in aliases if a["valid_from"]] == [
        ("FB", "2012-05-18"), ("META", "2022-06-09")
    ]
    store.close()


def test_existing_phase0_db_gets_phase1_columns(tmp_path: Path) -> None:
    db = tmp_path / "legacy.db"
    conn = __import__("sqlite3").connect(db)
    conn.execute("CREATE TABLE security_master (security_id TEXT PRIMARY KEY, ticker TEXT, name TEXT, exchange TEXT, market TEXT, cik TEXT, sector TEXT, industry TEXT, ipo_date TEXT, delisted_date TEXT, active INTEGER, created_at TEXT, updated_at TEXT)")
    conn.execute("CREATE TABLE ticker_aliases (alias TEXT, security_id TEXT, valid_from TEXT, valid_to TEXT, PRIMARY KEY(alias,security_id,valid_from))")
    conn.commit(); conn.close()
    store = SQLiteStore(db)
    store.connection
    store._apply_compatibility_migrations()
    cols = store._column_names("security_master")
    assert {"security_type", "composite_figi", "share_class_figi", "primary_exchange_mic"} <= cols
    store.close()


def test_finnhub_parser_is_validation_only() -> None:
    rows = FinnhubUniverseProvider.parse_symbol_payload([
        {"symbol": "AAPL", "displaySymbol": "AAPL", "description": "Apple Inc", "type": "Common Stock"}
    ])
    assert rows[0].symbol == "AAPL"
    assert rows[0].description == "Apple Inc"


class _SEC:
    async def list_current_us_securities(self):
        return []


class _MassiveOff:
    configured = False


class _FinnhubOff:
    configured = False


@pytest.mark.asyncio
async def test_historical_sync_fails_closed_without_massive(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "op.db")
    store.initialize(ROOT / "data" / "database" / "schema.sql")
    service = USUniverseService(
        SecurityRepository(store), sec=_SEC(), massive=_MassiveOff(), finnhub=_FinnhubOff()
    )
    with pytest.raises(RuntimeError, match="Historical US universe sync requires MASSIVE_API_KEY"):
        await service.sync(as_of=date(2025, 5, 5))
    store.close()


def test_exchange_mapping_and_cik_normalization() -> None:
    assert exchange_from_mic("XNAS") is Exchange.NASDAQ
    assert exchange_from_mic("XASE") is Exchange.AMEX
    assert exchange_from_mic("OTCM") is Exchange.OTC
    assert exchange_from_mic("BATS") is Exchange.CBOE
    assert normalize_cik("320193") == "0000320193"


def test_massive_upgrade_reuses_sec_fallback_security_id(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "upgrade.db")
    store.initialize(ROOT / "data" / "database" / "schema.sql")
    repo = SecurityRepository(store)
    sec_record = UniverseRecord(
        ticker="AAPL", name="Apple Inc.", exchange=Exchange.NASDAQ, exchange_mic="XNAS",
        active=True, provider="SEC_EDGAR", availability_date=NOW, cik="0000320193",
    )
    sec_id = repo.upsert_record(sec_record)
    massive_record = UniverseRecord(
        ticker="AAPL", name="Apple Inc.", exchange=Exchange.NASDAQ, exchange_mic="XNAS",
        active=True, provider="MASSIVE", availability_date=NOW, security_type="CS",
        cik="0000320193", composite_figi="BBG000B9XRY4", share_class_figi="BBG001S5N8V8",
    )
    massive_id = repo.upsert_record(massive_record)
    count = store.connection.execute("SELECT COUNT(*) AS n FROM security_master").fetchone()["n"]
    row = store.connection.execute("SELECT * FROM security_master WHERE security_id=?", (sec_id,)).fetchone()
    assert massive_id == sec_id
    assert count == 1
    assert row["share_class_figi"] == "BBG001S5N8V8"
    store.close()


def test_local_env_loader_does_not_override_existing_env(tmp_path: Path, monkeypatch) -> None:
    from core.config.env import load_local_env
    env_file = tmp_path / ".env"
    env_file.write_text("MASSIVE_API_KEY=file-value\nSEC_USER_AGENT=Example example@example.com\n")
    monkeypatch.setenv("MASSIVE_API_KEY", "process-value")
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    load_local_env(env_file)
    assert __import__("os").environ["MASSIVE_API_KEY"] == "process-value"
    assert __import__("os").environ["SEC_USER_AGENT"] == "Example example@example.com"
