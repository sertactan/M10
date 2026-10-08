from __future__ import annotations

import hashlib
import json
import sqlite3

import pytest

from data.database.sqlite_store import SQLiteStore
from scripts import phase14_sec_submissions_collect as collector
from scripts.phase14_sec_pilot_pipeline import pilot, PilotBlocked


CIK = "0000000123"
ACCESSION = "0000000123-25-000001"
ACCEPTED = "2025-08-09T18:00:00+00:00"
STAMP = "2026-10-08T12:00:00+00:00"
UA = "Meridyen Sec Evidence finance-contact@valid.org"
ARCHIVE = f"CIK{CIK}-submissions-001.json"
ROOT = f"CIK{CIK}.json"


def make_backup(tmp_path):
    backup = tmp_path / "operational_SEC_snapshot.db"
    with SQLiteStore(backup) as store:
        with store.connection:
            store.connection.execute(
                """INSERT INTO security_master
                   (security_id,ticker,name,exchange,market,cik,created_at,updated_at)
                   VALUES ('S1','DEMO','Demo','NASDAQ','US',?,?,?)""",
                (CIK, STAMP, STAMP),
            )
            store.connection.execute(
                """INSERT INTO fundamental_facts_source
                   (fact_id,security_id,metric_name,provider_metric_name,value,
                    unit,period_end,period_kind,filing_date,accepted_at,
                    available_at,source,source_document,accession_number,
                    retrieved_at,quality_status,validation_status,family,form_type)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                ("F1", "S1", "REVENUE", "Revenues", 100, "USD", "2025-06-30",
                 "QUARTERLY", "2025-08-09", None,
                 "2025-08-10T00:00:00+00:00", "SEC_EDGAR",
                 "https://data.sec.gov", ACCESSION, STAMP,
                 "AUTHORITATIVE", "SEC_CANONICAL", "REGULATORY", "10-Q"),
            )
    return backup


def make_root(*, archive=False):
    return {
        "cik": int(CIK),
        "filings": {
            "recent": {
                "accessionNumber": [ACCESSION],
                "acceptanceDateTime": [ACCEPTED],
                "form": ["10-Q"],
                "filingDate": ["2025-08-09"],
            },
            "files": [{"name": ARCHIVE}] if archive else [],
        },
    }


def archive_content():
    return {
        "accessionNumber": ["0000000123-13-000001"],
        "acceptanceDateTime": ["2013-08-09T17:00:00+00:00"],
        "form": ["10-Q"],
        "filingDate": ["2013-08-09"],
    }


def set_download_mock(monkeypatch, *, archive=False, counts=None):
    blobs = {ROOT: json.dumps(make_root(archive=archive)).encode()}
    if archive:
        blobs[ARCHIVE] = json.dumps(archive_content()).encode()
    calls = counts if counts is not None else []
    def stub(name, user_agent):
        assert user_agent == UA
        calls.append(name)
        return blobs[name]
    monkeypatch.setattr(collector, "_fetch_sec_document", stub)
    return calls


def test_without_sources_returns_explicit_missing_folder_and_no_write(tmp_path):
    backup = make_backup(tmp_path)
    before = backup.read_bytes()
    source = tmp_path / "private_sources"
    journal = tmp_path / "review" / "stage.sqlite3"
    result = pilot(backup, source, journal, cik=CIK)
    assert result["status"] == "WAITING_FOR_ORIGINAL_SEC_SOURCE_FOLDER"
    assert result["download_executed"] is False
    assert result["journal_modified"] is False
    assert not source.exists() and not journal.exists()
    assert backup.read_bytes() == before


def test_fully_mocked_sec_download_then_private_review_journal(tmp_path, monkeypatch):
    backup = make_backup(tmp_path)
    original = backup.read_bytes()
    source, journal = tmp_path / "SEC", tmp_path / "review" / "journal.sqlite3"
    calls = set_download_mock(monkeypatch)
    monkeypatch.setenv("SEC_USER_AGENT", UA)
    result = pilot(backup, source, journal, cik=CIK,
                   download=True, stage=True)
    assert calls == [ROOT]
    assert result["download_result"]["files_downloaded"] == 1
    assert result["status"] == "PRIVATE_EVIDENCE_REVIEW_STAGED_NOT_CANONICAL"
    assert result["evidence_preview"]["candidate_accessions"] == 1
    assert result["evidence_stage"]["new_rows"] == 1
    assert result["journal_modified"] is True
    assert result["historical_pit_certified"] is False
    assert result["production_db_modified"] is False
    assert backup.read_bytes() == original
    with sqlite3.connect(journal) as con:
        assert con.execute("SELECT count(*) FROM sec_acceptance_evidence").fetchone()[0] == 1
        assert con.execute(
            "SELECT sec_accepted_at FROM sec_acceptance_evidence"
        ).fetchone()[0] == ACCEPTED
    again = pilot(backup, source, journal, cik=CIK, stage=True)
    assert again["evidence_stage"]["new_rows"] == 0
    assert again["evidence_stage"]["reused_rows"] == 1
    assert calls == [ROOT]


def test_dry_preview_existing_sources_reads_but_does_not_write_journal(tmp_path, monkeypatch):
    backup = make_backup(tmp_path)
    source, journal = tmp_path / "SEC", tmp_path / "journal.sqlite3"
    set_download_mock(monkeypatch)
    monkeypatch.setenv("SEC_USER_AGENT", UA)
    first = pilot(backup, source, journal, cik=CIK, download=True)
    assert first["status"] == "EVIDENCE_PREVIEW_READY_NO_WRITES"
    assert not journal.exists()
    preview = pilot(backup, source, journal, cik=CIK, stage=False)
    assert preview["status"] == "EVIDENCE_PREVIEW_READY_NO_WRITES"
    assert preview["evidence_preview"]["candidate_accessions"] == 1
    assert preview["download_executed"] is False


def test_download_partials_do_not_stage_until_archives_complete(tmp_path, monkeypatch):
    backup = make_backup(tmp_path)
    source, journal = tmp_path / "SEC", tmp_path / "journal.sqlite3"
    calls = set_download_mock(monkeypatch, archive=True)
    monkeypatch.setenv("SEC_USER_AGENT", UA)
    first = pilot(backup, source, journal, cik=CIK,
                  download=True, stage=True, max_requests=1)
    assert first["status"] == "DOWNLOAD_STOPPED_RESUME_OR_REVIEW"
    assert first["download_result"]["error_code"] == "SEC_RUN_REQUEST_BUDGET_EXHAUSTED"
    assert not journal.exists()
    preview = pilot(backup, source, journal, cik=CIK, stage=True)
    assert preview["status"] == "WAITING_FOR_HISTORICAL_SEC_ARCHIVES"
    assert preview["journal_modified"] is False
    second = pilot(backup, source, journal, cik=CIK,
                   download=True, stage=True, max_requests=1)
    assert second["status"] == "PRIVATE_EVIDENCE_REVIEW_STAGED_NOT_CANONICAL"
    assert second["source_check"]["archive_files"] == 1
    assert second["evidence_stage"]["new_rows"] == 1
    assert calls == [ROOT, ARCHIVE]


def test_missing_backup_fails_before_download_and_creating_source_dir(tmp_path, monkeypatch):
    source = tmp_path / "sources"
    journal = tmp_path / "private" / "review.sqlite3"
    calls = []
    set_download_mock(monkeypatch, counts=calls)
    monkeypatch.setenv("SEC_USER_AGENT", UA)
    with pytest.raises(PilotBlocked, match="REQUIRES_EXISTING_OFFLINE_SQLITE_BACKUP"):
        pilot(tmp_path / "missing.db", source, journal, cik=CIK, download=True)
    assert not source.exists()
    assert not calls


def test_installed_operational_db_is_rejected_even_if_sqlite_is_valid(tmp_path, monkeypatch):
    path = make_backup(tmp_path)
    renamed = tmp_path / "operational.db"
    path.rename(renamed)
    monkeypatch.setenv("SEC_USER_AGENT", UA)
    with pytest.raises(PilotBlocked, match="LIVE_RUNTIME_DB_NOT_ALLOWED"):
        pilot(renamed, tmp_path / "evidence", tmp_path / "ledger.db",
              cik=CIK, download=True)


def test_missing_contact_blocks_before_making_network_or_files(tmp_path, monkeypatch):
    backup = make_backup(tmp_path)
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    source = tmp_path / "sec"
    with pytest.raises(ValueError, match="SEC_USER_AGENT"):
        pilot(backup, source, tmp_path / "journal.db", cik=CIK, download=True)
    assert not source.exists()


def test_mixed_issuer_root_files_fail_closed(tmp_path, monkeypatch):
    backup = make_backup(tmp_path)
    src = tmp_path / "sec"
    src.mkdir()
    (src / f"CIK{'0000000456'}.json").write_text("{}")
    with pytest.raises(PilotBlocked, match="ONE_ISSUER_PER_PILOT_FOLDER"):
        pilot(backup, src, tmp_path / "journal.sqlite3", cik=CIK, stage=True)
    assert not (tmp_path / "journal.sqlite3").exists()


def test_manually_edited_sec_document_fails_sha_verification(tmp_path, monkeypatch):
    backup = make_backup(tmp_path)
    src = tmp_path / "sec"
    journal = tmp_path / "review.sqlite3"
    set_download_mock(monkeypatch)
    monkeypatch.setenv("SEC_USER_AGENT", UA)
    pilot(backup, src, journal, cik=CIK, download=True)
    (src / ROOT).write_text((src / ROOT).read_text() + " ")
    with pytest.raises((ValueError, collector.CollectorBlocked), match="HASH"):
        pilot(backup, src, journal, cik=CIK, stage=True)
    assert not journal.exists()
