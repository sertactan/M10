from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from core.contracts.enums import Exchange
from core.universe.models import UniverseRecord
from data.database.sqlite_store import SQLiteStore
from data.providers.adanos_global_reference import AdanosGlobalReferenceProvider
from data.repositories.global_security_repository import GlobalSecurityRepository
from data.repositories.security_repository import SecurityRepository
from data.seeds import loader as seed_loader


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)


def test_global_reference_parser_keeps_collision_safe_listing_identity() -> None:
    text = """listing_key,ticker,exchange,name,asset_type,stock_sector,etf_category,country,country_code,isin,aliases,instrument_group_key,scope_reason
NASDAQ::AAPL,AAPL,NASDAQ,Apple Inc,Stock,Information Technology,,United States,US,US0378331005,apple,US0378331005,primary_listing
TSE::7203,7203,TSE,Toyota Motor Corp,Stock,Consumer Discretionary,,Japan,JP,JP3633400001,toyota,JP3633400001,primary_listing
HKEX::0700,0700,HKEX,Tencent Holdings Ltd,Stock,Communication Services,,Hong Kong,HK,HK070000865,腾讯,HK070000865,primary_listing
"""
    rows = AdanosGlobalReferenceProvider.parse_core_listings(text)
    assert len(rows) == 3
    assert rows[0].listing_key == "NASDAQ::AAPL"
    assert rows[1].market == "JP"
    assert rows[2].market == "HK"
    assert all(row.source_scope == "REFERENCE_ONLY" for row in rows)


def test_global_reference_enriches_canonical_us_row_without_downgrading_scope(
    tmp_path: Path,
) -> None:
    store = SQLiteStore(tmp_path / "ops.sqlite")
    store.initialize(ROOT / "data" / "database" / "schema.sql")
    try:
        canonical = SecurityRepository(store)
        sid = canonical.upsert_record(
            UniverseRecord(
                ticker="AAPL",
                name="Apple Inc.",
                exchange=Exchange.NASDAQ,
                exchange_mic="XNAS",
                active=True,
                provider="SEC_EDGAR",
                availability_date=NOW,
                cik="0000320193",
                currency="USD",
                locale="us",
            )
        )

        rows = AdanosGlobalReferenceProvider.parse_core_listings(
            """listing_key,ticker,exchange,name,asset_type,country,country_code,isin,aliases
NASDAQ::AAPL,AAPL,NASDAQ,Apple Inc,Stock,United States,US,US0378331005,apple
"""
        )
        count = GlobalSecurityRepository(store).bulk_upsert_reference(rows)
        assert count == 1

        row = store.connection.execute(
            "SELECT * FROM security_master WHERE security_id=?",
            (sid,),
        ).fetchone()
        assert row is not None
        assert row["source_scope"] == "CANONICAL"
        assert row["listing_key"] == "NASDAQ::AAPL"
        assert row["isin"] == "US0378331005"
        assert row["country_code"] == "US"
        assert row["asset_type"] == "Stock"
    finally:
        store.close()


def test_global_reference_stores_non_us_markets_locally(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "ops.sqlite")
    store.initialize(ROOT / "data" / "database" / "schema.sql")
    try:
        rows = AdanosGlobalReferenceProvider.parse_core_listings(
            """listing_key,ticker,exchange,name,asset_type,country,country_code,isin,aliases
TSE::7203,7203,TSE,Toyota Motor Corp,Stock,Japan,JP,JP3633400001,toyota
BIST::THYAO,THYAO,BIST,Turk Hava Yollari AO,Stock,Turkey,TR,TRATHYAO91M5,thy
HKEX::0700,0700,HKEX,Tencent Holdings Ltd,Stock,Hong Kong,HK,HK070000865,腾讯
"""
        )
        repo = GlobalSecurityRepository(store)
        assert repo.bulk_upsert_reference(rows) == 3
        assert len(repo.current_market("JP", asset_type="Stock")) == 1
        assert len(repo.current_market("TR", asset_type="Stock")) == 1
        assert len(repo.current_market("HK", asset_type="Stock")) == 1

        stored = store.connection.execute(
            "SELECT source_scope FROM security_master WHERE ticker='7203'"
        ).fetchone()
        assert stored["source_scope"] == "REFERENCE_ONLY"
    finally:
        store.close()


def test_bundled_sec_seed_bootstraps_full_us_reference_set(
    tmp_path: Path,
    monkeypatch,
) -> None:
    seed = tmp_path / "sec_us_current.csv"
    seed.write_text(
        """snapshot_date,ticker,name,exchange,exchange_mic,cik
2026-10-06,AAPL,Apple Inc.,NASDAQ,XNAS,0000320193
2026-10-06,OTCX,OTC Example,OTC,OTCM,0000000999
2026-10-06,CBOEX,CBOE Example,CBOE,BATS,0000001000
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(seed_loader, "bundled_sec_seed_path", lambda: seed)

    store = SQLiteStore(tmp_path / "ops.sqlite")
    store.initialize(ROOT / "data" / "database" / "schema.sql")
    try:
        assert seed_loader.bootstrap_bundled_us_seed(store) == 3
        repo = SecurityRepository(store)
        assert [row["ticker"] for row in repo.current_us_all_listings()] == [
            "CBOEX",
            "AAPL",
            "OTCX",
        ]
    finally:
        store.close()
