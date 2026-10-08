from __future__ import annotations

from pathlib import Path

from data.database.sqlite_store import SQLiteStore
from data.storage.parquet_price_store import ParquetPriceStore
from scripts.phase14_dataset_audit import audit


def _fixture(tmp_path: Path):
    db = tmp_path / "operational.db"
    st = SQLiteStore(db)
    st.initialize()
    now = "2026-10-08T00:00:00+00:00"
    st.connection.execute(
        """INSERT INTO security_master
           (security_id,ticker,name,exchange,market,active,created_at,updated_at)
           VALUES ('SEC_EX','EX','Example Inc','NASDAQ','US',0,?,?)""",
        (now,now),
    )
    st.connection.execute(
        """INSERT INTO universe_snapshot_membership
           (snapshot_date,security_id,ticker,exchange,exchange_mic,
            source,availability_date,ingested_at)
           VALUES ('2024-01-31','SEC_EX','EX','NASDAQ','XNAS',
                   'ALPHAVANTAGE_PIT',?,?)""",
        (now,now),
    )
    st.connection.execute(
        """INSERT INTO canonical_price_selection
           (selection_id,security_id,purpose,start_date,end_date,
            source,source_symbol,reason,selected_at)
           VALUES ('S','SEC_EX','BACKTEST_ADJUSTED','2024-01-01',
                   '2024-01-31','MASSIVE','EX','fixture',?)""",
        (now,),
    )
    st.connection.commit()
    st.close()
    price = tmp_path / "parquet"
    price.mkdir()
    return db,price


def test_missing_real_database_blocks_without_creating_db(tmp_path):
    db=tmp_path/"unmounted.db"
    result=audit(db,tmp_path/"prices")
    assert result["status"]=="BLOCKED"
    assert result["blockers"]==["M10_OPERATIONAL_DB_MISSING"]
    assert not db.exists()
    assert result["pit_independently_verified"] is False


def test_empty_initialized_database_reports_missing_monthly_pit(tmp_path):
    db=tmp_path/"operational.db"
    st=SQLiteStore(db)
    st.initialize()
    st.close()
    prices=tmp_path/"parquet"
    prices.mkdir()
    r=audit(db,prices,"2024-01-01","2024-02-29")
    assert r["requested_dates"]==2
    assert r["missing_snapshot_dates"]==["2024-01-31","2024-02-29"]
    assert "MISSING_MONTHLY_HISTORICAL_MEMBERSHIP" in r["blockers"]
    assert r["wf9_activated"] is False


def test_missing_canonical_physical_parquet_is_a_blocker(tmp_path):
    db,root=_fixture(tmp_path)
    r=audit(db,root,"2024-01-01","2024-01-31")
    assert "CANONICAL_SELECTION_WITHOUT_PARQUET_PARTITION" in r["blockers"]
    assert r["physical_prices"]["yearly_partitions_missing"]==1
    assert r["membership_counts_by_source"]["ALPHAVANTAGE_PIT"]==1
    assert r["pit_independently_verified"] is False


def test_physical_partition_present_does_not_claim_price_or_pit_certification(tmp_path):
    db,root=_fixture(tmp_path)
    store=ParquetPriceStore(root)
    path=store._year_path("MASSIVE","SEC_EX","EX",2024)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"placeholder-not-a-tested-price-bar")
    r=audit(db,root,"2024-01-01","2024-01-31")
    assert r["physical_prices"]["yearly_partitions_missing"]==0
    assert r["physical_prices"]["individual_bar_adjustments_verified"] is False
    assert r["status"]=="BLOCKED"
    assert "PARTIAL_PIT_PRICE_FUNDAMENTAL_OR_FEATURE_COVERAGE" in r["blockers"]


def test_incomplete_physical_audit_never_appears_ready(tmp_path):
    db,root=_fixture(tmp_path)
    r=audit(db,root,"2024-01-01","2024-01-31",price_checks=0)
    assert "PHYSICAL_PARQUET_AUDIT_INCOMPLETE" in r["blockers"]
    assert r["physical_prices"]["status"]=="CHECK_LIMIT_REACHED"
