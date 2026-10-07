from __future__ import annotations

import io
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from core.contracts.entities import Security
from core.contracts.enums import Exchange
from core.prices.adjustment import split_adjust_raw_close
from core.prices.engine import HistoricalPriceEngine
from core.prices.models import (
    AdjustmentStatus,
    PriceQualityStatus,
    PriceSeriesDescriptor,
    SourcePriceBar,
    SplitEvent,
)
from core.prices.policy import PriceSelectionPolicy, PriceSourceMixingError
from data.database.sqlite_store import SQLiteStore
from data.providers.marketparquet_price import MarketParquetPriceProvider
from data.providers.massive_price import MassivePriceProvider
from data.providers.simfin_price import SimFinPriceProvider
from data.providers.stooq_price import StooqPriceProvider
from data.providers.yahoo_price import YahooCompatiblePriceProvider
from data.repositories.price_repository import PriceRepository
from data.storage.parquet_price_store import ParquetPriceStore, REQUIRED_PRICE_COLUMNS

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
SEC = Security("SEC_TEST", "TEST", "Test Corp", Exchange.NASDAQ)


def test_all_price_providers_implement_common_surface() -> None:
    providers = [
        MassivePriceProvider("x"),
        StooqPriceProvider(),
        SimFinPriceProvider(),
        YahooCompatiblePriceProvider(),
        MarketParquetPriceProvider(),
    ]
    methods = {
        "get_history", "get_daily_bar", "get_market_snapshot", "get_splits",
        "get_dividends", "validate_symbol",
    }
    for provider in providers:
        assert methods <= set(dir(provider))


def test_massive_dual_aggregates_preserve_raw_and_adjusted_close() -> None:
    ts = int(datetime(2025, 1, 2, 14, 30, tzinfo=timezone.utc).timestamp() * 1000)
    raw = {"results": [{"t": ts, "o": 100, "h": 110, "l": 90, "c": 100, "v": 1000, "vw": 101}]}
    adjusted = {"results": [{"t": ts, "o": 50, "h": 55, "l": 45, "c": 50, "v": 2000}]}
    bars = MassivePriceProvider.parse_dual_aggregates("SEC_TEST", "TEST", raw, adjusted, retrieved_at=NOW)
    assert len(bars) == 1
    assert bars[0].raw_close == 100
    assert bars[0].adjusted_close == 50
    assert bars[0].source == "MASSIVE"
    assert bars[0].quality_status is PriceQualityStatus.PRIMARY
    assert bars[0].adjustment_status is AdjustmentStatus.DUAL_RAW_ADJUSTED


def test_massive_split_and_dividend_parsers() -> None:
    splits = MassivePriceProvider.parse_splits(
        "SEC_TEST", "TEST",
        {"results": [{"execution_date": "2025-01-03", "split_from": 1, "split_to": 10}]},
        retrieved_at=NOW,
    )
    dividends = MassivePriceProvider.parse_dividends(
        "SEC_TEST", "TEST",
        {"results": [{"ex_dividend_date": "2025-02-03", "cash_amount": 0.25, "currency": "USD"}]},
        retrieved_at=NOW,
    )
    assert splits[0].split_to == 10
    assert dividends[0].cash_amount == 0.25


def test_stooq_individual_csv_is_raw_bootstrap_not_fake_adjusted() -> None:
    text = "Date,Open,High,Low,Close,Volume\n2025-01-02,10,12,9,11,1000\n"
    bars = StooqPriceProvider.parse_individual_csv("SEC_TEST", "test.us", text, retrieved_at=NOW)
    assert bars[0].raw_close == 11
    assert bars[0].adjusted_close == 11
    assert bars[0].quality_status is PriceQualityStatus.BOOTSTRAP
    assert bars[0].adjustment_status is AdjustmentStatus.RAW_ONLY


def test_stooq_bulk_zip_ingestion(tmp_path: Path) -> None:
    zip_path = tmp_path / "stooq.zip"
    content = "<TICKER>,<PER>,<DATE>,<TIME>,<OPEN>,<HIGH>,<LOW>,<CLOSE>,<VOL>,<OPENINT>\nAAPL.US,D,20250102,000000,100,110,90,105,12345,0\n"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("data/us.txt", content)
    provider = StooqPriceProvider()
    bars = provider.ingest_bulk_zip(zip_path, security_lookup=lambda t: "SEC_AAPL" if t == "AAPL" else None, retrieved_at=NOW)
    assert len(bars) == 1
    assert bars[0].security_id == "SEC_AAPL"
    assert bars[0].source_symbol == "aapl.us"
    assert bars[0].trade_date == date(2025, 1, 2)


def test_simfin_bulk_parser_keeps_adj_close() -> None:
    frame = pd.DataFrame([{
        "Ticker": "TEST", "Date": "2025-01-02", "Open": 10, "High": 12,
        "Low": 9, "Close": 11, "Adj. Close": 5.5, "Volume": 1000,
    }])
    bars = SimFinPriceProvider.parse_frame("SEC_TEST", "TEST", frame, retrieved_at=NOW)
    assert bars[0].raw_close == 11
    assert bars[0].adjusted_close == 5.5
    assert bars[0].quality_status is PriceQualityStatus.SECONDARY


def test_yahoo_parser_is_fallback_only() -> None:
    ts = int(datetime(2025, 1, 2, 14, 30, tzinfo=timezone.utc).timestamp())
    payload = {"chart": {"result": [{
        "timestamp": [ts],
        "indicators": {
            "quote": [{"open": [10], "high": [12], "low": [9], "close": [11], "volume": [1000]}],
            "adjclose": [{"adjclose": [10.5]}],
        },
    }], "error": None}}
    bars = YahooCompatiblePriceProvider.parse_chart("SEC_TEST", "TEST", payload, retrieved_at=NOW)
    assert bars[0].adjusted_close == 10.5
    assert bars[0].quality_status is PriceQualityStatus.FALLBACK_ONLY


@pytest.mark.asyncio
async def test_yahoo_chart_falls_back_query2_to_query1_with_browser_headers(monkeypatch) -> None:
    provider = YahooCompatiblePriceProvider()
    calls = []

    payload = {"chart": {"result": [{
        "timestamp": [int(datetime(2025, 1, 2, tzinfo=timezone.utc).timestamp())],
        "indicators": {
            "quote": [{"open": [10], "high": [11], "low": [9], "close": [10.5], "volume": [1000]}],
            "adjclose": [{"adjclose": [10.5]}],
        },
    }], "error": None}}

    async def fake_get_json(url, *, params=None, headers=None):
        calls.append((url, headers))
        if "query2.finance.yahoo.com" in url:
            raise RuntimeError("HTTP 429 Too Many Requests")
        return payload

    monkeypatch.setattr(provider.http, "get_json", fake_get_json)
    bars = await provider.get_history(
        SEC,
        date(2025, 1, 1),
        date(2025, 1, 3),
    )
    assert len(bars) == 1
    assert "query2.finance.yahoo.com" in calls[0][0]
    assert "query1.finance.yahoo.com" in calls[1][0]
    assert calls[0][1]["User-Agent"].startswith("Mozilla/5.0")


def test_marketparquet_parser_accepts_delisted_symbol() -> None:
    frame = pd.DataFrame([{
        "symbol": "TEST-DELISTED", "date": "2025-01-02", "open": 10,
        "high": 12, "low": 9, "close": 11, "volume": 1000,
    }])
    bars = MarketParquetPriceProvider.parse_frame(
        "SEC_TEST", "TEST", frame, date(2025, 1, 1), date(2025, 1, 3), retrieved_at=NOW
    )
    assert len(bars) == 1
    assert bars[0].source_symbol == "TEST-DELISTED"
    assert bars[0].quality_status is PriceQualityStatus.SURVIVORSHIP_AWARE
    assert bars[0].adjustment_status is AdjustmentStatus.ADJUSTED_ONLY


def test_parquet_frame_contains_required_lineage_columns() -> None:
    bar = SourcePriceBar(
        security_id="SEC_TEST", source="MASSIVE", source_symbol="TEST", trade_date=date(2025, 1, 2),
        open=10, high=12, low=9, raw_close=11, adjusted_close=10.5, volume=1000,
        retrieved_at=NOW, quality_status=PriceQualityStatus.PRIMARY,
        adjustment_status=AdjustmentStatus.DUAL_RAW_ADJUSTED,
    )
    frame = ParquetPriceStore.bars_to_frame([bar])
    assert list(frame.columns) == REQUIRED_PRICE_COLUMNS
    for required in ["source", "source_symbol", "raw_close", "adjusted_close", "retrieved_at", "quality_status"]:
        assert required in frame.columns


def _desc(source: str, quality: PriceQualityStatus, adjustment: AdjustmentStatus) -> PriceSeriesDescriptor:
    return PriceSeriesDescriptor(
        security_id="SEC_TEST", source=source, source_symbol="TEST", start_date=date(2020, 1, 1),
        end_date=date(2025, 1, 1), row_count=1000, quality_status=quality,
        adjustment_status=adjustment, retrieved_at=NOW, content_hash=source,
    )


def test_policy_never_uses_yahoo_as_sole_authoritative_source() -> None:
    policy = PriceSelectionPolicy()
    yahoo = _desc("YAHOO_COMPAT", PriceQualityStatus.FALLBACK_ONLY, AdjustmentStatus.DUAL_RAW_ADJUSTED)
    with pytest.raises(PriceSourceMixingError):
        policy.select([yahoo], require_adjusted=True, authoritative=True)


def test_policy_skips_raw_stooq_and_selects_simfin_for_adjusted_backtest() -> None:
    policy = PriceSelectionPolicy()
    stooq = _desc("STOOQ", PriceQualityStatus.BOOTSTRAP, AdjustmentStatus.RAW_ONLY)
    simfin = _desc("SIMFIN", PriceQualityStatus.SECONDARY, AdjustmentStatus.DUAL_RAW_ADJUSTED)
    selected = policy.select([stooq, simfin], require_adjusted=True)
    assert selected.source == "SIMFIN"


def test_policy_rejects_mixed_series() -> None:
    b1 = SourcePriceBar("SEC_TEST","MASSIVE","TEST",date(2025,1,2),1,1,1,1,1,1,NOW,PriceQualityStatus.PRIMARY,AdjustmentStatus.DUAL_RAW_ADJUSTED)
    b2 = SourcePriceBar("SEC_TEST","YAHOO_COMPAT","TEST",date(2025,1,3),1,1,1,1,1,1,NOW,PriceQualityStatus.FALLBACK_ONLY,AdjustmentStatus.DUAL_RAW_ADJUSTED)
    with pytest.raises(PriceSourceMixingError):
        PriceSelectionPolicy.assert_single_source([b1,b2])


def test_split_adjustment_rejects_cross_provider_actions() -> None:
    bar = SourcePriceBar("SEC_TEST","STOOQ","test.us",date(2025,1,2),100,100,100,100,100,1,NOW,PriceQualityStatus.BOOTSTRAP,AdjustmentStatus.RAW_ONLY)
    split = SplitEvent("SEC_TEST","MASSIVE","TEST",date(2025,1,3),1,10,NOW,PriceQualityStatus.PRIMARY)
    with pytest.raises(PriceSourceMixingError):
        split_adjust_raw_close([bar],[split])


def test_split_adjustment_same_provider() -> None:
    bar = SourcePriceBar("SEC_TEST","MASSIVE","TEST",date(2025,1,2),100,100,100,100,100,1,NOW,PriceQualityStatus.PRIMARY,AdjustmentStatus.RAW_ONLY)
    split = SplitEvent("SEC_TEST","MASSIVE","TEST",date(2025,1,3),1,10,NOW,PriceQualityStatus.PRIMARY)
    adjusted = split_adjust_raw_close([bar],[split])
    assert adjusted[0].adjusted_close == 10


def test_phase2_schema_tables_exist(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "op.db")
    store.initialize(ROOT / "data" / "database" / "schema.sql")
    names = {r[0] for r in store.connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {
        "price_series_registry", "canonical_price_selection", "price_validation_results",
        "split_events_source", "dividend_events_source",
    } <= names
    store.close()


def test_parquet_partition_isolates_source_symbol(tmp_path: Path) -> None:
    store = ParquetPriceStore(tmp_path)
    a = store._year_path("MASSIVE", "SEC_META", "FB", 2021)
    b = store._year_path("MASSIVE", "SEC_META", "META", 2023)
    assert a != b
    assert "source_symbol=FB" in str(a)
    assert "source_symbol=META" in str(b)


@pytest.mark.asyncio
async def test_stooq_symbol_validation_uses_recent_window(monkeypatch) -> None:
    provider = StooqPriceProvider()
    seen = {}

    async def fake_history(security, start, end):
        seen["days"] = (end - start).days
        return [
            SourcePriceBar(
                security.security_id,
                "STOOQ",
                "test.us",
                end,
                1, 1, 1, 1, 1, 1,
                NOW,
                PriceQualityStatus.BOOTSTRAP,
                AdjustmentStatus.RAW_ONLY,
            )
        ]

    monkeypatch.setattr(provider, "get_history", fake_history)
    assert await provider.validate_symbol(SEC)
    assert seen["days"] == 15


@pytest.mark.asyncio
async def test_historical_price_engine_persists_actual_provider_coverage(tmp_path: Path):
    store = SQLiteStore(tmp_path / "coverage.db")
    store.initialize(ROOT / "data" / "database" / "schema.sql")
    now = NOW.isoformat()
    store.connection.execute(
        """
        INSERT INTO security_master (
            security_id,ticker,name,exchange,market,active,created_at,updated_at
        ) VALUES ('SEC_TEST','TEST','Test Corp','NASDAQ','US',1,?,?)
        """,
        (now, now),
    )
    store.connection.commit()

    class Provider:
        configured = True

        async def validate_symbol(self, security):
            return True

        async def get_history(self, security, start, end):
            return [
                SourcePriceBar(
                    security.security_id,
                    "SIMFIN",
                    security.ticker,
                    date(2020, 1, 2),
                    10, 11, 9, 10, 9.5, 1000,
                    NOW,
                    PriceQualityStatus.SECONDARY,
                    AdjustmentStatus.DUAL_RAW_ADJUSTED,
                ),
                SourcePriceBar(
                    security.security_id,
                    "SIMFIN",
                    security.ticker,
                    date(2024, 12, 31),
                    20, 21, 19, 20, 19.0, 2000,
                    NOW,
                    PriceQualityStatus.SECONDARY,
                    AdjustmentStatus.DUAL_RAW_ADJUSTED,
                ),
            ]

    repo = PriceRepository(store, ParquetPriceStore(tmp_path / "prices"))
    engine = HistoricalPriceEngine(repo, {"SIMFIN": Provider()})
    try:
        await engine.sync_history(
            SEC,
            date(2010, 1, 1),
            date(2026, 1, 1),
            provider="SIMFIN",
            require_adjusted=True,
            validate_with_fallback=False,
        )
        row = store.connection.execute(
            """
            SELECT start_date,end_date
            FROM canonical_price_selection
            WHERE security_id='SEC_TEST' AND purpose='BACKTEST_ADJUSTED'
            ORDER BY selected_at DESC
            LIMIT 1
            """
        ).fetchone()
        assert row["start_date"] == "2020-01-02"
        assert row["end_date"] == "2024-12-31"
    finally:
        store.close()
