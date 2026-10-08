from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import os
import sqlite3

import pytest

from data.database.sqlite_store import SQLiteStore
from scripts.phase14_identity_sec_audit import audit, _cik, _iso, _overlap

NOW="2026-10-08T10:00:00+00:00"


def fixture_db(tmp_path: Path):
    db=tmp_path/"runtime/data/runtime/operational.db"
    store=SQLiteStore(db)
    store.initialize()
    store.close()
    return db


def security(db, sid, ticker, cik, exchange="NASDAQ"):
    with sqlite3.connect(db) as c:
        c.execute(
            """INSERT INTO security_master
            (security_id,ticker,name,exchange,market,active,cik,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (sid,ticker,ticker+" LLC",exchange,"US",1,cik,NOW,NOW),
        )


def membership(db, sid, ticker="AAA"):
    with sqlite3.connect(db) as c:
        c.execute(
            """INSERT INTO universe_snapshot_membership
               (snapshot_date,security_id,ticker,exchange,exchange_mic,security_type,
               source,availability_date,ingested_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            ("2013-01-31",sid,ticker,"NASDAQ","XNAS","CS",
             "ALPHAVANTAGE_PIT",NOW,NOW),
        )


def fact(db, ident, *, accepted=None,
         available="2013-03-01T12:00:00+00:00",
         accession="0000000001-13-000001",
         filed="2013-02-28", period="2012-12-31"):
    with sqlite3.connect(db) as c:
        c.execute(
            """INSERT INTO fundamental_facts_source
            (fact_id,security_id,metric_name,provider_metric_name,value,unit,
             period_end,period_kind,filing_date,accepted_at,available_at,
             source,source_document,accession_number,retrieved_at,quality_status,
             validation_status,family)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (ident,"S1","REVENUE","Revenues",100,"USD",period,"QUARTERLY",
             filed,accepted,available,"SEC_EDGAR","https://sec.gov","0000000001-13-000001"
             if accession is not None else None,NOW,"AUTHORITATIVE","SEC_CANONICAL",
             "REGULATORY"),
        )


def filing(db, *, accepted="2013-03-01T14:00:00+00:00"):
    with sqlite3.connect(db) as c:
        c.execute(
            """INSERT INTO filing_records_source
            (filing_id,security_id,source,cik,form_type,filing_date,accepted_at,
             accession_number,retrieved_at)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            ("F1","S1","SEC_EDGAR","0000000001","10-K",
             "2013-02-28",accepted,"0000000001-13-000001",NOW),
        )


def test_clean_sample_is_not_pit_certified(tmp_path):
    db=fixture_db(tmp_path)
    security(db,"S1","AAA","1")
    membership(db,"S1")
    fact(db,"FACT1",accepted="2013-03-01T14:00:00+00:00",
         available="2013-03-01T14:00:00+00:00")
    filing(db)
    before=db.stat().st_size
    report=audit(db)
    assert report["status"]=="SAMPLED_NO_FLAGS_NOT_PIT_CERTIFIED"
    assert report["mode"]=="SQLITE_READ_ONLY_NO_NETWORK"
    assert report["identity"]["us_security_master_rows_examined"]==1
    assert report["sec_timing"]["latest_rows_sampled"]==1
    assert report["sec_timing"]["issues_in_sample"]=={}
    assert report["canonical_pit_identity_verified"] is False
    assert report["original_sec_filing_acceptance_verified"] is False
    assert report["wf9_activated"] is False
    assert db.stat().st_size==before


def test_missing_sec_acceptance_is_warning_not_false_pit(tmp_path):
    db=fixture_db(tmp_path)
    security(db,"S1","AAA","0000000001")
    fact(db,"FACT1",accepted=None,available="2013-03-02T00:00:00+00:00")
    rep=audit(db)
    assert rep["status"]=="EVIDENCE_GAPS_REQUIRE_RECONCILIATION"
    assert rep["sec_timing"]["issues_in_sample"]["FACT_ACCEPTANCE_TIMESTAMP_MISSING"]==1
    assert rep["sec_timing"]["issues_in_sample"]["FACT_ACCESSION_NOT_LINKED_TO_SEC_SUBMISSIONS"]==1
    assert "ORIGINAL_SEC_ACCEPTANCE_EVIDENCE_INCOMPLETE" in rep["warnings"]


def test_available_before_original_acceptance_fail_closed(tmp_path):
    db=fixture_db(tmp_path)
    security(db,"S1","AAA","0000000001")
    fact(db,"FACT1",accepted="2013-03-01T15:00:00+00:00",
         available="2013-03-01T12:00:00+00:00")
    filing(db,accepted="2013-03-01T15:00:00+00:00")
    rep=audit(db)
    assert rep["status"]=="IDENTITY_OR_TEMPORAL_CONFLICTS_REQUIRE_REVIEW"
    issues=rep["sec_timing"]["issues_in_sample"]
    assert issues["FACT_AVAILABLE_BEFORE_ACCEPTANCE"]==1
    assert issues["FACT_AVAILABLE_BEFORE_LINKED_FILING_ACCEPTANCE"]==1
    assert "SEC_TIME_INTEGRITY_CONFLICT_IN_SAMPLED_FACTS" in rep["errors"]


def test_linked_filing_acceptance_checks_bulk_fallback(tmp_path):
    db=fixture_db(tmp_path)
    security(db,"S1","AAA","0000000001")
    fact(db,"FACT1",accepted=None,available="2013-03-01T12:00:00+00:00")
    filing(db,accepted="2013-03-01T15:00:00+00:00")
    rep=audit(db)
    assert rep["sec_timing"]["issues_in_sample"]["FACT_AVAILABLE_BEFORE_LINKED_FILING_ACCEPTANCE"]==1
    assert "SEC_TIME_INTEGRITY_CONFLICT_IN_SAMPLED_FACTS" in rep["errors"]


def test_separate_ciks_same_ticker_flags_reuse_and_snapshot_collision(tmp_path):
    db=fixture_db(tmp_path)
    security(db,"S1","AAA","1")
    security(db,"S2","AAA","2")
    membership(db,"S1")
    membership(db,"S2")
    rep=audit(db,sec_sample=25)
    assert rep["identity"]["ticker_exchange_keys_with_distinct_known_ciks"]==1
    assert rep["identity"]["simultaneous_snapshot_identity_collision_count_lower_bound"]==1
    assert "SAME_SNAPSHOT_TICKER_MULTIPLE_SECURITY_IDS" in rep["errors"]


def test_same_cik_multiple_share_classes_not_automatically_flagged(tmp_path):
    db=fixture_db(tmp_path)
    security(db,"S1","AAA","1")
    security(db,"S2","AAA","0000000001")
    rep=audit(db)
    assert rep["identity"]["ticker_exchange_keys_with_distinct_known_ciks"]==0
    assert rep["status"]=="SAMPLED_NO_FLAGS_NOT_PIT_CERTIFIED"


def test_overlapping_known_alias_intervals_reported(tmp_path):
    db=fixture_db(tmp_path)
    security(db,"S1","AAA","1")
    security(db,"S2","BBB","2")
    with sqlite3.connect(db) as c:
        c.execute("""INSERT INTO ticker_aliases
            (alias,security_id,valid_from,valid_to) VALUES (?,?,?,?)""",
            ("QX","S1","2013-01-01","2013-12-31"))
        c.execute("""INSERT INTO ticker_aliases
            (alias,security_id,valid_from,valid_to) VALUES (?,?,?,?)""",
            ("QX","S2","2013-05-01","2014-01-31"))
    rep=audit(db)
    assert rep["identity"]["dated_alias_overlap_pairs"]==1
    assert "OVERLAPPING_DATED_TICKER_ALIASES_NEED_REVIEW" in rep["warnings"]


def test_missing_database_not_created(tmp_path):
    db=tmp_path/"missing.db"
    rep=audit(db)
    assert "LIVE_OPERATIONAL_DB_NOT_FOUND" in rep["errors"]
    assert not db.exists()


def test_sample_cap_blocks_unbounded_scans(tmp_path):
    with pytest.raises(ValueError,match="sec-sample"):
        audit(tmp_path/"missing",sec_sample=20001)


def test_timestamp_parsing_is_offset_aware_and_names_are_never_invented():
    assert _iso("2013-03-01T15:00:00+00:00") is not None
    assert _iso("2013-03-01T15:00:00") is None
    assert _iso("bad") is None
    assert _cik("0000000123")=="0000000123"
    assert _cik("123")=="0000000123"
    assert _cik("ABCD") is None
    assert _overlap("2013-01-01","2013-12-31","2013-05-01","2014-01-01")
    assert not _overlap("2013-01-01",None,"2013-05-01","2014-01-01")
