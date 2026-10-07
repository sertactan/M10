from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from core.fundamentals.models import (
    FactFamily,
    FundamentalFactRow,
    FundamentalQualityStatus,
    FundamentalValidationStatus,
    PeriodKind,
)
from core.research.walkforward_readiness import (
    SUPPORTED_MC_KEYS,
    V141_UPSTREAM_REQUIRED_KEYS,
    WalkForwardReadinessAuditor,
)
from data.database.sqlite_store import SQLiteStore
from data.repositories.fundamental_repository import FundamentalRepository
from data.repositories.model_feature_repository import ModelFeatureRepository


ROOT = Path(__file__).resolve().parents[1]
AS_OF_DATE = date(2026, 8, 20)
AS_OF = datetime(2026, 8, 20, 23, 59, tzinfo=timezone.utc)


def _store(tmp_path: Path, *, snapshot_source: str = "STOCK_DATA_PIT") -> SQLiteStore:
    store = SQLiteStore(tmp_path / "wf.sqlite")
    store.initialize(ROOT / "data" / "database" / "schema.sql")
    now = AS_OF.isoformat()
    store.connection.execute(
        """
        INSERT INTO security_master
        (security_id,ticker,name,exchange,market,cik,active,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?)
        """,
        ("SEC_TEST","TEST","Test Corp","NASDAQ","US","0000000123",1,now,now),
    )
    store.connection.execute(
        """
        INSERT INTO universe_snapshot_membership
        (snapshot_date,security_id,ticker,exchange,exchange_mic,security_type,
         source,availability_date,ingested_at)
        VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (
            AS_OF_DATE.isoformat(),"SEC_TEST","TEST","NASDAQ","XNAS","CS",
            snapshot_source,now,now,
        ),
    )
    store.connection.execute(
        """
        INSERT INTO canonical_price_selection
        (selection_id,security_id,purpose,start_date,end_date,source,source_symbol,reason,selected_at)
        VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (
            "SEL","SEC_TEST","BACKTEST","2020-01-01","2026-12-31",
            "STOOQ","TEST.US","test",now,
        ),
    )
    store.connection.commit()
    return store


def _add_fundamental(store: SQLiteStore) -> None:
    FundamentalRepository(store).save_facts([
        FundamentalFactRow(
            security_id="SEC_TEST",
            metric_name="REVENUE",
            provider_metric_name="Revenues",
            value=100.0,
            unit="USD",
            period_start=date(2025,1,1),
            period_end=date(2025,12,31),
            period_kind=PeriodKind.ANNUAL,
            filing_date=date(2026,2,1),
            accepted_at=datetime(2026,2,1,tzinfo=timezone.utc),
            available_at=datetime(2026,2,1,tzinfo=timezone.utc),
            source="SEC_EDGAR",
            source_document="https://www.sec.gov/test",
            accession_number="A1",
            retrieved_at=datetime(2026,2,1,tzinfo=timezone.utc),
            quality_status=FundamentalQualityStatus.AUTHORITATIVE,
            validation_status=FundamentalValidationStatus.SEC_CANONICAL,
            family=FactFamily.REGULATORY,
        )
    ])


def _add_v141_upstream(store: SQLiteStore) -> None:
    repo = ModelFeatureRepository(store)
    keys = list(V141_UPSTREAM_REQUIRED_KEYS) + [SUPPORTED_MC_KEYS[0]]
    for index, key in enumerate(keys, start=1):
        repo.save_feature(
            security_id="SEC_TEST",
            feature_key=key,
            value=float(50 + index),
            feature_as_of=AS_OF,
            available_at=AS_OF,
            source_phase="DERIVED_CANONICAL",
            source_ref="WF_TEST",
            quality_status="CANONICAL_DERIVED",
            computation_version="wf-test",
            evidence={"test": True},
        )


def test_walkforward_readiness_reports_exact_pit_and_full_evidence(tmp_path: Path) -> None:
    store = _store(tmp_path)
    try:
        _add_fundamental(store)
        _add_v141_upstream(store)
        row = WalkForwardReadinessAuditor(store).audit(AS_OF_DATE)
        assert row.universe_members == 1
        assert row.exact_pit_universe is True
        assert row.price_covered == 1
        assert row.fundamental_covered == 1
        assert row.feature_covered == 1
        assert row.v141_upstream_ready == 1
        assert row.blockers == ()
    finally:
        store.close()


def test_walkforward_readiness_rejects_current_universe_as_historical_pit(tmp_path: Path) -> None:
    store = _store(tmp_path, snapshot_source="SEC_EDGAR")
    try:
        row = WalkForwardReadinessAuditor(store).audit(AS_OF_DATE)
        assert row.exact_pit_universe is False
        assert "UNIVERSE_NOT_EXACT_PIT" in row.blockers
    finally:
        store.close()
