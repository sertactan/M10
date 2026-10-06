from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest

from app import data_bootstrap
from app.bootstrap import AppContainer
from core.prices.models import AdjustmentStatus, PriceQualityStatus, SourcePriceBar
from core.universe.models import UniverseRecord
from core.contracts.enums import Exchange
from data.repositories.security_repository import SecurityRepository


@pytest.mark.asyncio
async def test_first_run_bootstrap_populates_current_universe(tmp_path, monkeypatch):
    root = __import__("pathlib").Path(__file__).resolve().parents[1]
    monkeypatch.setenv("S153_RUNTIME_ROOT", str(tmp_path / "runtime"))
    app = AppContainer(root)
    app.initialize()
    try:
        now = datetime.now(timezone.utc)

        async def fake_list(self):
            return [
                UniverseRecord(
                    ticker="TEST",
                    name="Test Inc.",
                    exchange=Exchange.NASDAQ,
                    exchange_mic="XNAS",
                    active=True,
                    provider="SEC_EDGAR",
                    availability_date=now,
                    security_type="CS",
                    cik="0000000001",
                    currency="USD",
                    locale="us",
                )
            ]

        monkeypatch.setattr(
            data_bootstrap.SECEdgarUniverseProvider,
            "list_current_us_securities",
            fake_list,
        )

        count = await data_bootstrap.ensure_current_universe(app)
        assert count == 1
        rows = SecurityRepository(app.sqlite).current_us_common_stocks()
        assert rows[0]["ticker"] == "TEST"
    finally:
        app.close()


@pytest.mark.asyncio
async def test_price_bootstrap_persists_real_series_and_ui_selection(tmp_path, monkeypatch):
    root = __import__("pathlib").Path(__file__).resolve().parents[1]
    monkeypatch.setenv("S153_RUNTIME_ROOT", str(tmp_path / "runtime"))
    app = AppContainer(root)
    app.initialize()
    try:
        now = datetime(2026, 10, 6, 1, 0, tzinfo=timezone.utc)
        repo = SecurityRepository(app.sqlite)
        repo.bulk_upsert(
            [
                UniverseRecord(
                    ticker="TEST",
                    name="Test Inc.",
                    exchange=Exchange.NASDAQ,
                    exchange_mic="XNAS",
                    active=True,
                    provider="SEC_EDGAR",
                    availability_date=now,
                    security_type="CS",
                    cik="0000000001",
                    currency="USD",
                    locale="us",
                )
            ],
            snapshot_date=date(2026, 10, 6),
        )
        row = app.sqlite.connection.execute(
            "SELECT * FROM security_master WHERE ticker='TEST'"
        ).fetchone()

        async def fake_history(self, security, start, end):
            return [
                SourcePriceBar(
                    security_id=security.security_id,
                    source="YAHOO_COMPAT",
                    source_symbol=security.ticker,
                    trade_date=date(2026, 10, 5),
                    open=10.0,
                    high=11.0,
                    low=9.5,
                    raw_close=10.5,
                    adjusted_close=10.5,
                    volume=1000.0,
                    retrieved_at=now,
                    quality_status=PriceQualityStatus.FALLBACK_ONLY,
                    adjustment_status=AdjustmentStatus.DUAL_RAW_ADJUSTED,
                )
            ]

        monkeypatch.setattr(
            data_bootstrap.YahooCompatiblePriceProvider,
            "get_history",
            fake_history,
        )

        count = await data_bootstrap.ensure_price_history(
            app,
            row,
            as_of_date=date(2026, 10, 6),
        )
        assert count == 1

        selection = app.sqlite.connection.execute(
            """
            SELECT * FROM canonical_price_selection
            WHERE security_id=? AND purpose='UI_LIVE_FALLBACK'
            """,
            (row["security_id"],),
        ).fetchone()
        assert selection is not None
        assert selection["source"] == "YAHOO_COMPAT"

        feature = app.sqlite.connection.execute(
            """
            SELECT * FROM canonical_model_features
            WHERE security_id=? AND feature_key='RAW_CURRENT_PRICE'
            """,
            (row["security_id"],),
        ).fetchone()
        assert feature is not None
        assert feature["value"] == pytest.approx(10.5)
    finally:
        app.close()


@pytest.mark.asyncio
async def test_price_bootstrap_falls_back_to_stooq_after_yahoo_429(tmp_path, monkeypatch):
    root = __import__("pathlib").Path(__file__).resolve().parents[1]
    monkeypatch.setenv("S153_RUNTIME_ROOT", str(tmp_path / "runtime"))
    app = AppContainer(root)
    app.initialize()
    try:
        now = datetime(2026, 10, 6, 1, 0, tzinfo=timezone.utc)
        repo = SecurityRepository(app.sqlite)
        repo.bulk_upsert(
            [
                UniverseRecord(
                    ticker="TEST",
                    name="Test Inc.",
                    exchange=Exchange.NASDAQ,
                    exchange_mic="XNAS",
                    active=True,
                    provider="SEC_EDGAR",
                    availability_date=now,
                    security_type="CS",
                    cik="0000000001",
                    currency="USD",
                    locale="us",
                )
            ],
            snapshot_date=date(2026, 10, 6),
        )
        row = app.sqlite.connection.execute(
            "SELECT * FROM security_master WHERE ticker='TEST'"
        ).fetchone()

        async def yahoo_429(self, security, start, end):
            raise RuntimeError("HTTP 429 Too Many Requests")

        async def stooq_history(self, security, start, end):
            return [
                SourcePriceBar(
                    security_id=security.security_id,
                    source="STOOQ",
                    source_symbol="test.us",
                    trade_date=date(2026, 10, 5),
                    open=20.0,
                    high=21.0,
                    low=19.0,
                    raw_close=20.5,
                    adjusted_close=20.5,
                    volume=2000.0,
                    retrieved_at=now,
                    quality_status=PriceQualityStatus.BOOTSTRAP,
                    adjustment_status=AdjustmentStatus.RAW_ONLY,
                )
            ]

        monkeypatch.setattr(
            data_bootstrap.YahooCompatiblePriceProvider,
            "get_history",
            yahoo_429,
        )
        monkeypatch.setattr(
            data_bootstrap.StooqPriceProvider,
            "get_history",
            stooq_history,
        )

        count = await data_bootstrap.ensure_price_history(
            app,
            row,
            as_of_date=date(2026, 10, 6),
        )
        assert count == 1

        selection = app.sqlite.connection.execute(
            """
            SELECT * FROM canonical_price_selection
            WHERE security_id=? AND purpose='UI_LIVE_BOOTSTRAP'
            ORDER BY selected_at DESC
            LIMIT 1
            """,
            (row["security_id"],),
        ).fetchone()
        assert selection is not None
        assert selection["source"] == "STOOQ"

        yahoo_event = app.sqlite.connection.execute(
            """
            SELECT * FROM provider_health_events
            WHERE provider='YAHOO_COMPAT'
            ORDER BY event_id DESC
            LIMIT 1
            """
        ).fetchone()
        assert yahoo_event is not None
        assert yahoo_event["success"] == 0
        assert yahoo_event["rate_limited"] == 1
    finally:
        app.close()
