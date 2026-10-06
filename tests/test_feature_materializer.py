from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from app.bootstrap import AppContainer
from app.feature_materializer import CanonicalFeatureMaterializer
from core.contracts.enums import Exchange
from core.features.s153_v12_input_loader import S153V12InputLoader
from core.fundamentals.models import (
    FactFamily,
    FundamentalFactRow,
    FundamentalQualityStatus,
    FundamentalValidationStatus,
    PeriodKind,
)
from core.prices.models import AdjustmentStatus, PriceQualityStatus, SourcePriceBar
from core.universe.models import UniverseRecord
from data.repositories.fundamental_repository import FundamentalRepository
from data.repositories.price_repository import PriceRepository
from data.repositories.security_repository import SecurityRepository
from data.storage.parquet_price_store import ParquetPriceStore


AS_OF_DATE = date(2026, 10, 6)
AS_OF = datetime.combine(AS_OF_DATE, time.max, tzinfo=timezone.utc)


def _fact(
    security_id: str,
    metric: str,
    value: float,
    period_end: date,
    *,
    kind: PeriodKind = PeriodKind.ANNUAL,
) -> FundamentalFactRow:
    available = datetime(
        period_end.year + 1,
        2,
        15,
        12,
        0,
        tzinfo=timezone.utc,
    )
    return FundamentalFactRow(
        security_id=security_id,
        metric_name=metric,
        provider_metric_name=metric,
        value=value,
        unit="USD" if metric != "SHARES_OUTSTANDING" else "shares",
        period_start=(date(period_end.year, 1, 1) if kind is PeriodKind.ANNUAL else None),
        period_end=period_end,
        filing_date=available.date(),
        accepted_at=available,
        available_at=available,
        source="SEC_EDGAR",
        source_document="https://www.sec.gov/test",
        accession_number=f"{metric}-{period_end.year}",
        retrieved_at=AS_OF,
        quality_status=FundamentalQualityStatus.AUTHORITATIVE,
        validation_status=FundamentalValidationStatus.SEC_CANONICAL,
        family=FactFamily.REGULATORY,
        period_kind=kind,
        form_type="10-K",
    )


def test_materializer_bridges_price_and_sec_into_model_features(tmp_path: Path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("S153_RUNTIME_ROOT", str(tmp_path / "runtime"))
    app = AppContainer(root)
    app.initialize()
    try:
        now = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
        SecurityRepository(app.sqlite).bulk_upsert(
            [
                UniverseRecord(
                    ticker="TEST",
                    name="Test Corp",
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
            snapshot_date=AS_OF_DATE,
        )
        row = app.sqlite.connection.execute(
            "SELECT * FROM security_master WHERE ticker='TEST'"
        ).fetchone()
        sid = row["security_id"]

        start = AS_OF_DATE - timedelta(days=320)
        bars = []
        for i in range(230):
            day = start + timedelta(days=i)
            price = 10.0 + i * 0.05
            bars.append(
                SourcePriceBar(
                    security_id=sid,
                    source="YAHOO_COMPAT",
                    source_symbol="TEST",
                    trade_date=day,
                    open=price - 0.1,
                    high=price + 0.2,
                    low=price - 0.2,
                    raw_close=price,
                    adjusted_close=price,
                    volume=100_000 + i * 500,
                    retrieved_at=now,
                    quality_status=PriceQualityStatus.FALLBACK_ONLY,
                    adjustment_status=AdjustmentStatus.DUAL_RAW_ADJUSTED,
                )
            )
        prices = PriceRepository(
            app.sqlite,
            ParquetPriceStore(app.resolve_data_path(app.app_config.database.parquet_root)),
        )
        desc = prices.save_series(bars)
        prices.select_series(
            security_id=sid,
            start=desc.start_date,
            end=AS_OF_DATE,
            source=desc.source,
            source_symbol=desc.source_symbol,
            purpose="UI_LIVE_FALLBACK",
            reason="test canonical price window",
        )

        facts = []
        revenues = [100, 115, 140, 180, 240, 330]
        operating = [5, 8, 14, 25, 42, 70]
        gross = [40, 47, 60, 80, 112, 165]
        eps = [0.5, 0.7, 1.0, 1.5, 2.2, 3.4]
        ocf = [8, 12, 20, 35, 55, 85]
        capex = [4, 5, 6, 8, 10, 12]
        shares = [120, 118, 116, 114, 112, 110]
        for offset, year in enumerate(range(2020, 2026)):
            pe = date(year, 12, 31)
            facts.extend(
                [
                    _fact(sid, "REVENUE", revenues[offset], pe),
                    _fact(sid, "OPERATING_INCOME", operating[offset], pe),
                    _fact(sid, "GROSS_PROFIT", gross[offset], pe),
                    _fact(sid, "DILUTED_EPS", eps[offset], pe),
                    _fact(sid, "OPERATING_CASH_FLOW", ocf[offset], pe),
                    _fact(sid, "CAPEX", capex[offset], pe),
                    _fact(
                        sid,
                        "SHARES_OUTSTANDING",
                        shares[offset],
                        pe,
                        kind=PeriodKind.INSTANT,
                    ),
                ]
            )
        facts.append(
            _fact(
                sid,
                "CASH",
                60.0,
                date(2025, 12, 31),
                kind=PeriodKind.INSTANT,
            )
        )
        FundamentalRepository(app.sqlite).save_facts(facts)

        count = CanonicalFeatureMaterializer(app).materialize(
            row,
            as_of_date=AS_OF_DATE,
        )
        assert count >= 12

        loaded = S153V12InputLoader(
            __import__("data.repositories.model_feature_repository", fromlist=["ModelFeatureRepository"]).ModelFeatureRepository(app.sqlite)
        ).load(security_id=sid, ticker="TEST", as_of=AS_OF)

        assert loaded.current_price is not None
        assert loaded.current_market_cap is not None
        assert loaded.discovery_factors[1] is not None
        assert loaded.discovery_factors[3] is not None
        assert loaded.control_factors["GP"] is not None
        assert loaded.control_factors["DIL"] is not None
        assert loaded.features["OL_Q"] is not None
        assert loaded.features["MI_Q"] is not None
        assert loaded.features["FCFI_Q"] is not None
        assert loaded.features["TURNACC"] is not None
        assert loaded.features["PIT_INTEGRITY"] == 100.0
    finally:
        app.close()
