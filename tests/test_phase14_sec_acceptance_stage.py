from __future__ import annotations

from datetime import datetime, timezone
import json
import sqlite3

import pytest

from data.database.sqlite_store import SQLiteStore
from scripts.phase14_sec_acceptance_stage import (
    exact_utc, filing_rows, normalize_cik, stage
)


NOW = "2026-10-08T11:00:00+00:00"


def setup(tmp_path, *, duplicate_cik=False):
    db = tmp_path / "runtime" / "data/runtime/operational.db"
    store = SQLiteStore(db)
    store.initialize()
    with store.connection:
        store.connection.execute(
            """INSERT INTO security_master
            (security_id,ticker,name,exchange,market,active,cik,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            ("S1", "TEST", "Test Inc", "NASDAQ", "US", 1, "0000000123", NOW, NOW),
        )
        if duplicate_cik:
            store.connection.execute(
                """INSERT INTO security_master
                (security_id,ticker,name,exchange,market,active,cik,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                ("S2", "TEST.B", "Test Class B", "NASDAQ", "US", 1, "123", NOW, NOW),
            )
        store.connection.execute(
            """INSERT INTO fundamental_facts_source
            (fact_id,security_id,metric_name,provider_metric_name,value,unit,
             period_end,period_kind,filing_date,accepted_at,available_at,
             source,source_document,accession_number,retrieved_at,
             quality_status,validation_status,family)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("FACT1", "S1", "REVENUE", "Revenues", 1, "USD", "2013-06-30",
             "QUARTERLY", "2013-08-09", None,
             "2013-08-10T00:00:00+00:00",
             "SEC_EDGAR", "https://sec.gov", "0000000123-13-000001", NOW,
             "AUTHORITATIVE", "SEC_CANONICAL", "REGULATORY"),
        )
    store.close()
    source = tmp_path / "CIK0000000123.json"
    source.write_text(json.dumps({
        "cik": 123,
        "filings": {"recent": {
            "accessionNumber": ["0000000123-13-000001"],
            "acceptanceDateTime": ["2013-08-09T18:00:00.000Z"],
            "form": ["10-Q"], "filingDate": ["2013-08-09"],
        }}
    }), encoding="utf-8")
    return db, source


def test_offline_stage_is_read_only_and_not_canonical(tmp_path):
    db, source = setup(tmp_path)
    before_db = db.read_bytes()
    r = stage(db, source)
    assert r["status"] == "EVIDENCE_STAGED_REVIEW_REQUIRED"
    assert r["matched_security_count"] == 1
    assert r["counts"]["evidence_rows_staged"] == 1
    assert r["staged"][0]["eligible_for_later_review"] is True
    assert r["staged"][0]["sec_accepted_at"] == "2013-08-09T18:00:00+00:00"
    assert r["original_acceptance_evidence_complete"] is False
    assert r["historical_pit_certified"] is False
    assert r["wf9_activated"] is False
    assert db.read_bytes() == before_db
    with sqlite3.connect(db) as conn:
        assert conn.execute(
            "SELECT accepted_at FROM fundamental_facts_source WHERE fact_id='FACT1'"
        ).fetchone()[0] is None


def test_share_class_same_cik_is_ambiguous(tmp_path):
    db, source = setup(tmp_path, duplicate_cik=True)
    r = stage(db, source)
    assert r["status"] == "BLOCKED_CIK_IDENTITY_AMBIGUOUS"
    assert r["matched_security_count"] == 2
    assert not r["staged"]


def test_source_timestamp_must_be_explicit_timezone(tmp_path):
    db, source = setup(tmp_path)
    payload = json.loads(source.read_text())
    payload["filings"]["recent"]["acceptanceDateTime"] = ["2013-08-09T18:00:00"]
    source.write_text(json.dumps(payload))
    r = stage(db, source)
    assert r["status"] == "NO_SAFE_MATCHES_REQUIRE_REVIEW"
    assert r["counts"]["no_authoritative_offset_aware_acceptance"] == 1
    assert "evidence_rows_staged" not in r["counts"]


def test_existing_availability_prior_to_filing_is_lookahead(tmp_path):
    db, source = setup(tmp_path)
    with sqlite3.connect(db) as conn:
        conn.execute(
            """UPDATE fundamental_facts_source SET
               available_at='2013-08-09T16:00:00+00:00' WHERE fact_id='FACT1'"""
        )
    r = stage(db, source)
    assert r["counts"]["lookahead_available_before_accepted"] == 1
    assert r["status"] == "NO_SAFE_MATCHES_REQUIRE_REVIEW"


def test_missing_or_malformed_source_never_creates_database(tmp_path):
    db = tmp_path / "not-existing.db"
    source = tmp_path / "subs.json"
    source.write_text(json.dumps({
        "cik": 123,
        "filings": {"recent": {
            "accessionNumber": [], "acceptanceDateTime": [], "form": [],
            "filingDate": []
        }}
    }))
    with pytest.raises(ValueError, match="Existing|Actual installed"):
        stage(db, source)
    assert not db.exists()
    assert not (tmp_path/"not-existing.db-wal").exists()


def test_malformed_or_misaligned_arrays_rejected():
    with pytest.raises(ValueError, match="Misaligned"):
        filing_rows({"filings": {"recent": {
            "accessionNumber":["123"],"acceptanceDateTime":[],
            "form":["10-Q"],"filingDate":["2013-08-09"]
        }}})
    with pytest.raises(ValueError, match="CIK"):
        normalize_cik("unknown")
    assert exact_utc("2013-08-09T18:00:00") is None
    assert exact_utc("2013-08-09T18:00:00Z").utcoffset().total_seconds() == 0


def test_oversize_sample_prevents_high_db_load(tmp_path):
    db, source = setup(tmp_path)
    with pytest.raises(ValueError, match="max_facts"):
        stage(db, source, max_facts=0)
