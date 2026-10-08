from __future__ import annotations

import hashlib
import json
import sqlite3

import pytest

from data.database.sqlite_store import SQLiteStore
from scripts.phase14_sec_acceptance_evidence_journal import (
    EvidenceBlocked, STAGE, stage_evidence,
)
from scripts.phase14_sec_submissions_collect import (
    HOST, SCHEMA as COLLECTOR_SCHEMA,
)


CIK = "0000000123"
ACCESSION = "0000000123-25-000001"
WHEN = "2026-10-08T12:00:00+00:00"
ACCEPTED = "2025-08-09T18:00:00+00:00"


def fixture_sources(tmp_path, *, origin="FETCHED_FROM_PINNED_SEC_HTTPS_ENDPOINT",
                    available="2025-08-10T00:00:00+00:00", with_history=False):
    # This is a synthetic fixture, not actual SEC provenance.
    backup = tmp_path / "offline_backup.db"
    store = SQLiteStore(backup)
    store.initialize()
    with store.connection:
        store.connection.execute(
            """INSERT INTO security_master
               (security_id,ticker,name,exchange,market,cik,created_at,updated_at)
               VALUES ('S1','DEMO','DEMO','NASDAQ','US',?,?,?)""",
            (CIK, WHEN, WHEN),
        )
        store.connection.execute(
            """INSERT INTO fundamental_facts_source
               (fact_id,security_id,metric_name,provider_metric_name,value,
                unit,period_end,period_kind,filing_date,accepted_at,
                available_at,source,source_document,accession_number,
                retrieved_at,quality_status,validation_status,family,form_type)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("FACT1","S1","REVENUE","Revenues",100,"USD","2025-06-30",
             "QUARTERLY","2025-08-09",None,available,"SEC_EDGAR",
             "https://data.sec.gov",ACCESSION,WHEN,"AUTHORITATIVE",
             "SEC_CANONICAL","REGULATORY","10-Q"),
        )
    store.close()
    sources = tmp_path / "SEC"
    sources.mkdir()
    name = f"CIK{CIK}.json"
    historical_name = f"CIK{CIK}-submissions-001.json"
    root = {
        "cik": int(CIK),
        "filings": {
            "recent": {
                "accessionNumber": [ACCESSION],
                "acceptanceDateTime": [ACCEPTED],
                "form": ["10-Q"],
                "filingDate": ["2025-08-09"],
            },
            "files": [{"name": historical_name}] if with_history else [],
        },
    }
    data = json.dumps(root).encode()
    (sources / name).write_bytes(data)
    manifest = {
        "schema": COLLECTOR_SCHEMA,
        "documents": {
            name: {
                "origin": origin,
                "url": HOST + name,
                "sha256": hashlib.sha256(data).hexdigest(),
                "size_bytes": len(data),
                "retrieved_at_utc": WHEN,
                "source_authenticity_independently_verified": False,
            },
        },
    }
    if with_history:
        manifest["documents"][historical_name] = {
            "origin": origin,
            "url": HOST + historical_name,
            "sha256": "0" * 64,
            "size_bytes": 0,
            "retrieved_at_utc": WHEN,
            "source_authenticity_independently_verified": False,
        }
        # We deliberately do not create historical file: a partial root pilot
        # can yield candidates but CANNOT claim full archival coverage.
    (sources / "sec_sources_manifest.json").write_text(json.dumps(manifest))
    return backup, sources, tmp_path / "review" / "evidence.sqlite3"


def test_preview_does_not_create_journal_or_modify_snapshot(tmp_path):
    backup, source, journal = fixture_sources(tmp_path)
    before = backup.read_bytes()
    result = stage_evidence(backup, source, journal)
    assert result["status"] == "PREVIEW_REVIEW_REQUIRED"
    assert result["candidate_accessions"] == 1
    assert result["source_provenance_manifest_checked"] is True
    assert not journal.exists()
    assert backup.read_bytes() == before
    assert result["historical_pit_certified"] is False
    assert result["wf9_activated"] is False


def test_execute_stages_one_immutable_candidate_and_idempotently_replays(tmp_path):
    backup, source, journal = fixture_sources(tmp_path)
    original = backup.read_bytes()
    first = stage_evidence(backup, source, journal, execute=True)
    assert first["status"] == "EVIDENCE_STAGED_FOR_MANUAL_REVIEW"
    assert first["new_rows"] == 1 and first["reused_rows"] == 0
    assert first["original_sec_acceptance_independently_certified"] is False
    with sqlite3.connect(journal) as con:
        stored = con.execute(
            "SELECT cik,accession_number,sec_accepted_at,stage_status,matched_facts "
            "FROM sec_acceptance_evidence"
        ).fetchone()
        assert stored == (CIK, ACCESSION, ACCEPTED, STAGE, 1)
    second = stage_evidence(backup, source, journal, execute=True)
    assert second["new_rows"] == 0 and second["reused_rows"] == 1
    with sqlite3.connect(journal) as con:
        assert con.execute("SELECT COUNT(*) FROM sec_acceptance_evidence").fetchone()[0] == 1
    assert backup.read_bytes() == original


def test_tampered_source_blocks_before_creating_any_journal(tmp_path):
    backup, source, journal = fixture_sources(tmp_path)
    (source / f"CIK{CIK}.json").write_text(
        (source / f"CIK{CIK}.json").read_text() + " "
    )
    with pytest.raises(EvidenceBlocked, match="HASH_MISMATCH"):
        stage_evidence(backup, source, journal, execute=True)
    assert not journal.exists()


def test_unverified_local_source_cannot_enter_review_journal(tmp_path):
    backup, source, journal = fixture_sources(
        tmp_path, origin="PREEXISTING_LOCAL_SOURCE_NOT_VERIFIED"
    )
    with pytest.raises(EvidenceBlocked, match="PREEXISTING_SOURCE_UNVERIFIED"):
        stage_evidence(backup, source, journal, execute=True)
    assert not journal.exists()


def test_reconcile_rejects_lookahead_and_never_creates_journal(tmp_path):
    backup, source, journal = fixture_sources(
        tmp_path, available="2025-08-09T12:00:00+00:00"
    )
    result = stage_evidence(backup, source, journal, execute=True)
    assert result["status"] == "NO_EVIDENCE_ELIGIBLE_NOTHING_WRITTEN"
    assert result["candidate_accessions"] == 0
    assert result["reconciliation_counts"]["rejected_available_before_sec_acceptance"] == 1
    assert not journal.exists()


def test_conflicting_second_evidence_is_not_silently_overwritten(tmp_path):
    backup, source, journal = fixture_sources(tmp_path)
    stage_evidence(backup, source, journal, execute=True)
    with sqlite3.connect(journal) as con:
        con.execute(
            "UPDATE sec_acceptance_evidence SET sec_accepted_at=?",
            ("2025-08-09T19:00:00+00:00",),
        )
    with pytest.raises(EvidenceBlocked, match="CONFLICT_EXISTING_JOURNAL"):
        stage_evidence(backup, source, journal, execute=True)
    with sqlite3.connect(journal) as con:
        assert con.execute("SELECT COUNT(*) FROM sec_acceptance_evidence").fetchone()[0] == 1
        assert con.execute(
            "SELECT sec_accepted_at FROM sec_acceptance_evidence"
        ).fetchone()[0] == "2025-08-09T19:00:00+00:00"


def test_missing_old_archive_does_not_certify_coverage(tmp_path):
    backup, source, journal = fixture_sources(tmp_path, with_history=True)
    result = stage_evidence(backup, source, journal, execute=True)
    assert result["new_rows"] == 1
    assert result["archival_coverage_complete"] is False
    assert result["reconciliation_counts"]["missing_archival_documents"] == 1
    assert result["historical_pit_certified"] is False


def test_never_write_journal_inside_public_repo_or_sources(tmp_path):
    backup, source, _ = fixture_sources(tmp_path)
    with pytest.raises(EvidenceBlocked, match="OVERLAPS"):
        stage_evidence(backup, source, source / "journal.db")
    (tmp_path / ".git").mkdir()
    with pytest.raises(EvidenceBlocked, match="OUTSIDE_GIT"):
        stage_evidence(backup, source, tmp_path / "evidence.db")
    assert not (tmp_path / "evidence.db").exists()


def test_no_unmounted_backup_created_from_typo(tmp_path):
    _, source, journal = fixture_sources(tmp_path)
    missing = tmp_path / "wrong_db.db"
    with pytest.raises(EvidenceBlocked, match="EXISTING_OFFLINE"):
        stage_evidence(missing, source, journal, execute=True)
    assert not missing.exists()


def test_invalid_source_download_manifest_fails_closed(tmp_path):
    backup, source, journal = fixture_sources(tmp_path)
    p = source / "sec_sources_manifest.json"
    data = json.loads(p.read_text())
    data["documents"][f"CIK{CIK}.json"]["url"] = "https://evil.invalid/file"
    p.write_text(json.dumps(data))
    with pytest.raises(EvidenceBlocked, match="URL_MISMATCH"):
        stage_evidence(backup, source, journal, execute=True)
    assert not journal.exists()
