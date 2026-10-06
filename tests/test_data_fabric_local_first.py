from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from app import data_bootstrap
from app.bootstrap import AppContainer
from app.ui.analysis_service import DesktopAnalysisService
from core.contracts.enums import Exchange
from core.prices.models import AdjustmentStatus, PriceQualityStatus, SourcePriceBar
from core.universe.models import UniverseRecord
from data.repositories.price_repository import PriceRepository
from data.repositories.security_repository import SecurityRepository
from data.storage.parquet_price_store import ParquetPriceStore


def _seed_cached_price(app: AppContainer):
    now = datetime(2026, 10, 5, 22, 0, tzinfo=timezone.utc)
    security_repo = SecurityRepository(app.sqlite)
    security_repo.bulk_upsert(
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
        snapshot_date=date(2026, 10, 5),
    )
    row = app.sqlite.connection.execute(
        "SELECT * FROM security_master WHERE ticker='TEST'"
    ).fetchone()
    parquet = ParquetPriceStore(
        app.resolve_data_path(app.app_config.database.parquet_root)
    )
    repo = PriceRepository(app.sqlite, parquet)
    bars = [
        SourcePriceBar(
            security_id=row["security_id"],
            source="YAHOO_COMPAT",
            source_symbol="TEST",
            trade_date=date(2026, 10, 4),
            open=9.0,
            high=10.5,
            low=8.5,
            raw_close=10.0,
            adjusted_close=10.0,
            volume=900.0,
            retrieved_at=now,
            quality_status=PriceQualityStatus.FALLBACK_ONLY,
            adjustment_status=AdjustmentStatus.DUAL_RAW_ADJUSTED,
        ),
        SourcePriceBar(
            security_id=row["security_id"],
            source="YAHOO_COMPAT",
            source_symbol="TEST",
            trade_date=date(2026, 10, 5),
            open=10.0,
            high=11.5,
            low=9.5,
            raw_close=11.0,
            adjusted_close=11.0,
            volume=1000.0,
            retrieved_at=now,
            quality_status=PriceQualityStatus.FALLBACK_ONLY,
            adjustment_status=AdjustmentStatus.DUAL_RAW_ADJUSTED,
        ),
    ]
    descriptor = repo.save_series(bars)
    repo.select_series(
        security_id=row["security_id"],
        start=date(2026, 10, 4),
        end=date(2026, 10, 5),
        source=descriptor.source,
        source_symbol=descriptor.source_symbol,
        purpose="UI_LIVE_FALLBACK",
        reason="seed last-known-good",
    )
    return row


@pytest.mark.asyncio
async def test_price_bootstrap_uses_last_known_good_when_live_provider_fails(
    tmp_path, monkeypatch
):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("S153_RUNTIME_ROOT", str(tmp_path / "runtime"))
    app = AppContainer(root)
    app.initialize()
    try:
        row = _seed_cached_price(app)

        async def fail_history(self, security, start, end):
            raise RuntimeError("network unavailable")

        monkeypatch.setattr(
            data_bootstrap.YahooCompatiblePriceProvider,
            "get_history",
            fail_history,
        )

        count = await data_bootstrap.ensure_price_history(
            app,
            row,
            as_of_date=date(2026, 10, 6),
        )
        assert count == 0

        event = app.sqlite.connection.execute(
            """
            SELECT * FROM provider_health_events
            WHERE provider='YAHOO_COMPAT'
            ORDER BY event_id DESC
            LIMIT 1
            """
        ).fetchone()
        assert event is not None
        assert event["success"] == 0
    finally:
        app.close()


def test_desktop_header_marks_last_known_good_price_as_stale(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("S153_RUNTIME_ROOT", str(tmp_path / "runtime"))
    app = AppContainer(root)
    app.initialize()
    try:
        row = _seed_cached_price(app)
        service = DesktopAnalysisService(root)
        header = service._load_stock(app, row, date(2026, 10, 6))
        assert header.status == "CACHED STALE PRICE"
        assert header.price == pytest.approx(11.0)
        assert header.price_date == "2026-10-05"
        assert header.price_source.startswith("LKG")
    finally:
        app.close()
