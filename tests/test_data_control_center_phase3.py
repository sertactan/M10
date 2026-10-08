from __future__ import annotations

import json
import os
import sqlite3
import zipfile
from datetime import datetime, timezone

import pytest

from app.sec_import_progress import SECImportProgress, SECImportBusy, PROGRESS_FILE, LOCK_FILE, SCHEMA
from app.bulk_data_bootstrap import import_sec_companyfacts_zip
from app.ui.data_control_center_service import DataControlCenterService
from data.database.sqlite_store import SQLiteStore


def _test_runtime(tmp_path):
    runtime = tmp_path / "installed"
    db = runtime / "data/runtime/operational.db"
    store = SQLiteStore(db)
    store.initialize()
    now = datetime.now(timezone.utc).isoformat()
    store.connection.execute(
        """INSERT INTO security_master
           (security_id,ticker,name,exchange,market,cik,active,created_at,updated_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        ("SEC_1", "TEST", "Test Inc", "NASDAQ", "US", "0000000001", 1, now, now),
    )
    store.connection.commit()
    return runtime, store


def test_progress_writer_stages_and_ends_without_db_changes(tmp_path):
    archive = tmp_path / "bulk/sec"
    assert not archive.exists()
    with SECImportProgress(archive, checkpoint_every=2) as progress:
        state = json.loads((archive / PROGRESS_FILE).read_text())
        assert state["schema"] == SCHEMA
        assert state["stage"] == "STARTING"
        assert (archive / LOCK_FILE).exists()
        progress.checkpoint(entries_total=4, entries_scanned=2,
                            securities=1, facts=17)
        state = json.loads((archive / PROGRESS_FILE).read_text())
        assert state["entries_scanned"] == 2
        assert state["facts_written_this_run"] == 17
        with pytest.raises(SECImportBusy):
            with SECImportProgress(archive):
                pass
    state = json.loads((archive / PROGRESS_FILE).read_text())
    assert state["stage"] == "FINISHED"
    assert state["complete_archive_processed"] is False
    assert state["independently_verified"] is False
    assert not (archive / LOCK_FILE).exists()


def test_progress_failure_keeps_report_but_removes_owned_lock(tmp_path):
    folder = tmp_path / "sec"
    with pytest.raises(RuntimeError, match="deliberate"):
        with SECImportProgress(folder) as progress:
            progress.checkpoint(entries_total=3, entries_scanned=1)
            raise RuntimeError("deliberate")
    assert json.loads((folder / PROGRESS_FILE).read_text())["stage"] == "FAILED"
    assert not (folder / LOCK_FILE).exists()


def test_existing_lock_fail_closed_without_cleanup(tmp_path):
    folder = tmp_path / "sec"
    folder.mkdir()
    lock = folder / LOCK_FILE
    lock.write_text('{"pid":123}')
    with pytest.raises(SECImportBusy):
        with SECImportProgress(folder):
            pass
    assert lock.read_text() == '{"pid":123}'


def test_import_sec_zip_generates_real_checkpoints_and_quality_sample(tmp_path):
    runtime, store = _test_runtime(tmp_path)
    archive = runtime / "bulk/sec"
    archive.mkdir(parents=True)
    zip_path = archive / "companyfacts.zip"
    facts = {"facts": {"us-gaap": {"Revenues": {"units": {
        "USD": [{
            "start":"2024-01-01", "end":"2024-12-31", "val":10,
            "accn":"0000000001-25-000001", "fy":2024, "fp":"FY",
            "form":"10-K", "filed":"2025-02-15",
        }]
    }}}}}
    with zipfile.ZipFile(zip_path, "w") as archive_file:
        archive_file.writestr("CIK0000000001.json", json.dumps(facts))
    try:
        saved, n = import_sec_companyfacts_zip(
            type("TestApp", (), {"sqlite":store})(), zip_path
        )
        assert (saved, n) == (1, 1)
        checkpoint = json.loads((archive / PROGRESS_FILE).read_text())
        assert checkpoint["stage"] == "FINISHED"
        assert checkpoint["complete_archive_processed"] is True
        assert checkpoint["entries_total"] == 1
        assert checkpoint["entries_scanned"] == 1
        assert checkpoint["matched_issuers_saved"] == 1
        assert checkpoint["facts_written_this_run"] == 1
        assert not (archive / LOCK_FILE).exists()
        sample = DataControlCenterService(runtime_root=runtime).snapshot().phase3
        assert sample.sec_checkpoint_stage == "FINISHED"
        assert sample.sec_checkpoint_status == "RUN_REPORTED_FINISHED_NOT_INDEPENDENTLY_VERIFIED"
        assert sample.sec_quality_rows_sampled == 1
        assert sample.sec_quality_missing_accepted_at == 1
        assert sample.sec_quality_missing_accession == 0
        assert sample.sec_import_verified_complete is False
        assert sample.readiness_control == "MANUAL_OPERATOR_CONFIRMATION_REQUIRED_LEGACY_UNDETECTABLE"
    finally:
        store.close()


def test_quality_sampling_detects_lookahead_without_updating_db(tmp_path):
    runtime, store = _test_runtime(tmp_path)
    now = datetime.now(timezone.utc).isoformat()
    with store.connection:
        store.connection.execute(
            """INSERT INTO fundamental_facts_source
               (fact_id,security_id,metric_name,provider_metric_name,value,unit,
                period_end,period_kind,filing_date,accepted_at,available_at,
                source,source_document,accession_number,retrieved_at,
                quality_status,validation_status,family)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("F1", "SEC_1", "REVENUE", "Revenues", 5, "USD",
             "2024-12-31", "ANNUAL", "2025-02-15",
             "2025-02-15T20:00:00+00:00", "2025-02-15T18:00:00+00:00",
             "SEC_EDGAR", "source", None, now, "PRIMARY", "CHECK", "REVENUE"),
        )
    before = store.connection.execute(
        "SELECT accepted_at,available_at FROM fundamental_facts_source WHERE fact_id='F1'"
    ).fetchone()
    view = DataControlCenterService(runtime_root=runtime).snapshot().phase3
    assert view.sec_quality_rows_sampled == 1
    assert view.sec_quality_time_order_conflicts == 1
    assert view.sec_quality_missing_accession == 1
    after = store.connection.execute(
        "SELECT accepted_at,available_at FROM fundamental_facts_source WHERE fact_id='F1'"
    ).fetchone()
    assert tuple(before) == tuple(after)
    store.close()


def test_old_import_without_lock_is_unknown_not_safe(tmp_path):
    runtime, store = _test_runtime(tmp_path)
    view = DataControlCenterService(runtime_root=runtime).snapshot().phase3
    assert view.sec_checkpoint_status == "NO_INSTRUMENTED_SEC_RUN"
    assert view.sec_lock_present is False
    assert view.sec_import_verified_complete is False
    assert "MANUAL_OPERATOR_CONFIRMATION_REQUIRED" in view.readiness_control
    store.close()


def test_lock_shows_active_and_checkpoint_not_marked_complete(tmp_path):
    runtime, store = _test_runtime(tmp_path)
    folder = runtime / "bulk/sec"
    with SECImportProgress(folder) as progress:
        progress.checkpoint(entries_total=250, entries_scanned=10,
                            securities=5, facts=500)
        view = DataControlCenterService(runtime_root=runtime).snapshot().phase3
        assert view.sec_checkpoint_status == "LOCK_PRESENT_PROGRESS_ONLY"
        assert view.sec_lock_present is True
        assert view.sec_entries_scanned == 10
        assert view.sec_entries_total == 250
        assert view.readiness_control == "BLOCKED_ACTIVE_SEC_LOCK"
        assert view.sec_import_verified_complete is False
    store.close()


def test_invalid_progress_json_is_not_success(tmp_path):
    runtime, store = _test_runtime(tmp_path)
    folder = runtime / "bulk/sec"
    folder.mkdir(parents=True)
    (folder / PROGRESS_FILE).write_text(json.dumps({
        "schema":"INVALID_SCHEMA", "stage":"FINISHED",
        "entries_total": 250, "entries_scanned":250
    }))
    view = DataControlCenterService(runtime_root=runtime).snapshot().phase3
    assert view.sec_checkpoint_status == "INVALID_SEC_CHECKPOINT"
    assert view.sec_import_verified_complete is False
    store.close()
