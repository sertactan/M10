from __future__ import annotations

from datetime import date
import json
import sqlite3

import pytest

from data.database.sqlite_store import SQLiteStore
from scripts.phase14_sec_submissions_archive_reconcile import reconcile

NOW = "2026-10-08T12:00:00+00:00"
CIK = "0000000123"


def _fixture(tmp_path, *, share_class=False, archival=True, missing_archive=False):
    db = tmp_path / "readonly_snapshot.db"
    store = SQLiteStore(db)
    store.initialize()
    with store.connection:
        store.connection.execute(
            """INSERT INTO security_master
               (security_id,ticker,name,exchange,market,cik,created_at,updated_at)
               VALUES ('SEC1','ABC','ABC Inc','NASDAQ','US',?, ?, ?)""",
            (CIK, NOW, NOW),
        )
        if share_class:
            store.connection.execute(
                """INSERT INTO security_master
                   (security_id,ticker,name,exchange,market,cik,created_at,updated_at)
                   VALUES ('SEC2','ABC.B','ABC B','NASDAQ','US',?, ?, ?)""",
                (CIK, NOW, NOW),
            )
        for fact, acc, filed, accepted in [
            ("FACT_OLD", "0000000123-13-000001", "2013-08-09", "2013-08-10T00:00:00+00:00"),
            ("FACT_NEW", "0000000123-25-000001", "2025-08-09", "2025-08-10T00:00:00+00:00"),
        ]:
            store.connection.execute(
                """INSERT INTO fundamental_facts_source
                   (fact_id,security_id,metric_name,provider_metric_name,value,
                    unit,period_end,period_kind,filing_date,accepted_at,
                    available_at,source,source_document,accession_number,
                    retrieved_at,quality_status,validation_status,family,form_type)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (fact, "SEC1", "REVENUE", "Revenues", 100, "USD",
                 "2013-06-30" if fact == "FACT_OLD" else "2025-06-30",
                 "QUARTERLY", filed, None, accepted, "SEC_EDGAR",
                 "https://data.sec.gov", acc, NOW, "AUTHORITATIVE",
                 "SEC_CANONICAL", "REGULATORY", "10-Q"),
            )
    store.close()
    folder = tmp_path / "SEC_sources"
    folder.mkdir()
    archive_name = f"CIK{CIK}-submissions-001.json"
    (folder / f"CIK{CIK}.json").write_text(json.dumps({
        "cik": int(CIK),
        "filings": {
            "recent": {
                "accessionNumber": ["0000000123-25-000001"],
                "acceptanceDateTime": ["2025-08-09T18:00:00.000Z"],
                "form": ["10-Q"], "filingDate": ["2025-08-09"],
            },
            "files": [{"name": archive_name}] if archival else [],
        },
    }))
    if archival and not missing_archive:
        (folder / archive_name).write_text(json.dumps({
            "accessionNumber": ["0000000123-13-000001"],
            "acceptanceDateTime": ["2013-08-09T18:00:00Z"],
            "form": ["10-Q"], "filingDate": ["2013-08-09"],
        }))
    return db, folder


def test_reconcile_main_and_history_is_read_only(tmp_path):
    db, folder = _fixture(tmp_path)
    original = db.read_bytes()
    report = reconcile(db, folder)
    assert report["status"] == "EVIDENCE_CANDIDATES_REVIEW_REQUIRED"
    assert report["counts"]["issuer_root_documents_loaded"] == 1
    assert report["counts"]["archival_documents_loaded"] == 1
    assert report["counts"]["facts_with_reviewable_evidence"] == 2
    assert report["archival_coverage_complete"] is True
    assert len(report["evidence_candidates"]) == 2
    assert next(c for c in report["evidence_candidates"]
                if c["accession_number"].endswith("13-000001"))["source_filename"].endswith(
                    "-submissions-001.json")
    assert report["historical_pit_certified"] is False
    assert report["wf9_activated"] is False
    assert db.read_bytes() == original
    with sqlite3.connect(db) as con:
        assert con.execute(
            "SELECT COUNT(*) FROM fundamental_facts_source WHERE accepted_at IS NULL"
        ).fetchone()[0] == 2


def test_missing_archive_does_not_claim_complete_coverage(tmp_path):
    db, folder = _fixture(tmp_path, missing_archive=True)
    report = reconcile(db, folder)
    assert report["counts"]["missing_archival_documents"] == 1
    assert report["archival_coverage_complete"] is False
    assert report["counts"]["facts_with_reviewable_evidence"] == 1


def test_share_classes_same_cik_are_fail_closed(tmp_path):
    db, folder = _fixture(tmp_path, share_class=True)
    report = reconcile(db, folder)
    assert report["counts"]["issuer_identity_ambiguous_or_missing"] == 1
    assert not report["evidence_candidates"]
    assert report["status"] == "NO_SAFE_MATCHING_EVIDENCE"
    assert report["conflicts"][0]["matched_security_count"] == 2


def test_conflicting_acceptance_duplicates_never_emit_candidate(tmp_path):
    db, folder = _fixture(tmp_path, archival=False)
    root = folder / f"CIK{CIK}.json"
    payload = json.loads(root.read_text())
    recent = payload["filings"]["recent"]
    for k in ("accessionNumber", "acceptanceDateTime", "form", "filingDate"):
        recent[k] *= 2
    recent["acceptanceDateTime"][1] = "2025-08-09T19:00:00Z"
    root.write_text(json.dumps(payload))
    report = reconcile(db, folder)
    assert report["counts"]["conflicting_duplicate_accessions"] == 1
    assert not report["evidence_candidates"]


def test_bad_fact_availability_quarantines_whole_accession(tmp_path):
    db, folder = _fixture(tmp_path, archival=False)
    with sqlite3.connect(db) as conn:
        conn.execute(
            """UPDATE fundamental_facts_source
               SET available_at='2025-08-09T17:00:00+00:00'
               WHERE fact_id='FACT_NEW'"""
        )
    result = reconcile(db, folder)
    assert result["counts"]["rejected_available_before_sec_acceptance"] == 1
    assert not result["evidence_candidates"]


def test_source_hash_only_not_origin_certificate_and_missing_db(tmp_path):
    db, folder = _fixture(tmp_path, archival=False)
    result = reconcile(db, folder)
    assert result["independent_sec_download_provenance_verified"] is False
    with pytest.raises(ValueError, match="Existing SQLite"):
        reconcile(tmp_path / "missing.db", folder)
    assert not (tmp_path / "missing.db").exists()


def test_reject_traversal_and_wrong_root_cik(tmp_path):
    db, folder = _fixture(tmp_path)
    root = folder / f"CIK{CIK}.json"
    payload = json.loads(root.read_text())
    payload["filings"]["files"][0]["name"] = "../other.json"
    root.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="archive name"):
        reconcile(db, folder)
    payload["filings"]["files"] = []
    payload["cik"] = 999
    root.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="root document CIK"):
        reconcile(db, folder)


def test_global_reconciliation_limit_is_reported(tmp_path):
    db, folder = _fixture(tmp_path)
    result = reconcile(db, folder, max_accessions=1)
    assert result["counts"]["accessions_deferred_by_run_limit"] == 1
    assert len(result["evidence_candidates"]) == 1
    assert result["historical_pit_certified"] is False


def test_bad_stored_form_is_not_accepted(tmp_path):
    db, folder = _fixture(tmp_path, archival=False)
    with sqlite3.connect(db) as conn:
        conn.execute(
            """UPDATE fundamental_facts_source SET form_type='10-K'
               WHERE fact_id='FACT_NEW'"""
        )
    result = reconcile(db, folder)
    assert result["counts"]["rejected_fact_form_mismatch"] == 1
    assert not result["evidence_candidates"]


def test_accession_pages_do_not_repeat_evidence(tmp_path):
    db, folder = _fixture(tmp_path)
    first = reconcile(db, folder, max_accessions=1, accession_offset=0)
    second = reconcile(db, folder, max_accessions=1, accession_offset=1)
    assert first["next_accession_offset"] == 1
    assert second["next_accession_offset"] is None
    assert first["evidence_candidates"][0]["accession_number"] != (
        second["evidence_candidates"][0]["accession_number"]
    )


def test_malformed_duplicate_rejects_previously_valid_source(tmp_path):
    db, folder = _fixture(tmp_path, archival=False)
    root = folder / f"CIK{CIK}.json"
    payload = json.loads(root.read_text())
    recent = payload["filings"]["recent"]
    for k in ("accessionNumber", "acceptanceDateTime", "form", "filingDate"):
        recent[k] *= 2
    recent["acceptanceDateTime"][1] = "2025-08-09T19:00:00"  # missing offset
    root.write_text(json.dumps(payload))
    result = reconcile(db, folder)
    assert result["counts"]["acceptance_missing_offset"] == 1
    assert not result["evidence_candidates"]
