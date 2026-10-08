from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from app.ui.data_control_center_service import DataControlCenterService
from app.ui.data_control_center_dialog import DataControlCenterDialog
from app.ui.main_window import ResearchTerminalWindow
from data.database.sqlite_store import SQLiteStore


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def seeded_runtime(tmp_path):
    runtime = tmp_path / "installed"
    db = runtime / "data/runtime/operational.db"
    store = SQLiteStore(db)
    store.initialize()
    now = datetime.now(timezone.utc).isoformat()
    store.connection.execute(
        """INSERT INTO security_master
        (security_id,ticker,name,exchange,market,active,cik,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        ("SEC_1","TEST","Test Corp","NASDAQ","US",1,"0000123456",now,now),
    )
    for month in ("2013-01-31","2013-02-28"):
        store.connection.execute(
            """INSERT INTO universe_snapshot_membership
                (snapshot_date,security_id,ticker,exchange,exchange_mic,
                 security_type,source,availability_date,ingested_at)
                VALUES (?,?,?,?,?,?,?,?,?)""",
            (month,"SEC_1","TEST","NASDAQ","XNAS","CS","ALPHAVANTAGE_PIT",month,now),
        )
    store.connection.execute(
        """INSERT INTO fundamental_facts_source(
        fact_id,security_id,metric_name,provider_metric_name,value,unit,
        period_start,period_end,period_kind,filing_date,accepted_at,available_at,
        source,source_document,accession_number,retrieved_at,
        quality_status,validation_status,family)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("FACT_1","SEC_1","REVENUE","Revenue",100,"USD",None,"2013-01-31",
         "QUARTERLY","2013-02-25",None,"2013-02-26","SEC_EDGAR","test",
         None,now,"PRIMARY","PASS","GROWTH"),
    )
    store.connection.execute(
        """INSERT INTO price_series_registry(
        series_id,security_id,source,source_symbol,start_date,end_date,row_count,
        quality_status,adjustment_status,retrieved_at,content_hash,parquet_root,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("PRICE_1","SEC_1","MASSIVE","TEST","2024-10-08","2024-12-31",
         59,"PRIMARY","DUAL_RAW_ADJUSTED",now,"a"*64,"test",now),
    )
    store.connection.execute(
        """INSERT INTO canonical_price_selection
        (selection_id,security_id,purpose,start_date,end_date,source,
         source_symbol,reason,selected_at) VALUES (?,?,?,?,?,?,?,?,?)""",
        (str(uuid.uuid4()),"SEC_1","PHASE14_ADJUSTED_PILOT_UNVERIFIED",
         "2024-10-08","2024-12-31","MASSIVE","TEST","pilot",now),
    )
    store.connection.commit()
    store.close()
    return runtime, db


def test_read_only_panel_counts_and_blocks_wf9_certification(tmp_path):
    runtime, db = seeded_runtime(tmp_path)
    view = DataControlCenterService(runtime_root=runtime).snapshot()
    assert view.pit_target == 144
    assert view.pit_present == 2
    assert view.pit_missing == 142
    assert view.first_missing_month == "2013-03-31"
    assert view.sec_cik_mapped_us == 1
    assert view.sec_fact_rows == 1
    assert view.price_series == 1
    assert view.adjusted_series == 1
    assert view.reported_adjusted_bar_rows == 59
    assert view.pilot_price_selections == 1
    assert view.backtest_adjusted_selections == 0
    assert view.wf5_run_rows == 0
    assert "HISTORICAL_MONTHLY_PIT_LISTINGS_INCOMPLETE" in view.blockers
    assert "NO_CANONICAL_BACKTEST_ADJUSTED_SELECTIONS" in view.blockers
    assert view.wf9_activated_by_this_panel is False
    with sqlite3.connect(db) as con:
        assert con.execute(
            "SELECT COUNT(*) FROM fundamental_facts_source"
        ).fetchone()[0] == 1
    assert not list(runtime.rglob("*.json"))


def test_missing_local_db_never_creates_one(tmp_path):
    root=tmp_path/"not-installed"
    out=DataControlCenterService(runtime_root=root).snapshot()
    assert "LOCAL_OPERATIONAL_DB_NOT_FOUND" in out.blockers
    assert out.sec_fact_rows is None
    assert out.pit_present is None
    assert not root.exists()


def test_auto_refresh_not_enabled_and_dialog_disclaimer(qapp, tmp_path):
    runtime, _=seeded_runtime(tmp_path)
    view=DataControlCenterService(runtime_root=runtime).snapshot()
    dialog=DataControlCenterDialog(service_factory=None, auto_load=False)
    try:
        assert dialog.table.rowCount() == 0
        dialog.apply_snapshot(view)
        assert dialog.table.rowCount() >= 15
        assert dialog.table.item(0,1).text() == "2/144"
        assert "1" in dialog.table.item(2,1).text()
        assert dialog.table.item(14,1).text() == "NO"
        assert "no database writes" in dialog.status.text().lower()
        assert "HISTORICAL_MONTHLY_PIT_LISTINGS_INCOMPLETE" in dialog.blockers.text()
    finally:
        dialog.close()


def test_desktop_has_data_control_button_and_fails_closed_without_backend(qapp):
    window=ResearchTerminalWindow()
    try:
        assert window.control_center_button.text()=="DATA CONTROL"
        window.control_center_button.click()
        assert window.status.text()=="Data Control Center backend is not connected"
    finally:
        window.close()



def test_phase2_shows_sec_archive_but_never_certifies_import(tmp_path):
    import json
    runtime, db = seeded_runtime(tmp_path)
    sec = runtime / "bulk" / "sec"
    sec.mkdir(parents=True)
    (sec / "companyfacts.zip").write_bytes(b"zip fixture bytes")
    preflight = runtime / "data" / "runtime" / "phase13_readiness"
    preflight.mkdir(parents=True)
    (preflight / "PHASE13_READINESS.json").write_text(json.dumps({
        "schema": "MERIDYEN_PHASE13_READINESS_V1",
        "generated_at": "2020-01-01T00:00:00+00:00",
        "status": "PREFLIGHT_READY_NOT_ACTIVATED",
        "blockers": [],
        "wf9_activated": False,
    }))
    pit = runtime / "data" / "runtime" / "pit_daily_sync"
    pit.mkdir(parents=True)
    (pit / "latest_status.json").write_text(json.dumps({
        "schema": "MERIDYEN_DAILY_PIT_SYNC_V1",
        "status": "DAILY_REQUEST_BUDGET_REACHED",
        "utc_date": "2026-10-08",
        "api_requests_recorded_today_by_this_tool": 16,
        "daily_limit_for_this_tool": 20,
    }))
    view = DataControlCenterService(runtime_root=runtime).snapshot()
    assert view.phase2 is not None
    assert view.phase2.sec_archive_status == "SEC_ARCHIVE_PRESENT_IMPORT_UNVERIFIED"
    assert view.phase2.sec_import_completion_verified is False
    assert view.phase2.sec_archive_size_mb is not None
    assert view.phase2.wf9_report_status == "PREFLIGHT_READY_NOT_ACTIVATED"
    assert view.phase2.wf9_report_stale is True
    assert view.phase2.daily_pit_requests_used == 16
    assert view.phase2.daily_pit_requests_limit == 20
    assert ("2013", 2) in view.phase2.pit_year_coverage
    assert ("2014", 0) in view.phase2.pit_year_coverage
    assert view.wf9_activated_by_this_panel is False
    assert view.phase2.adjusted_sources[0][0] == "MASSIVE"
    assert view.phase2.adjusted_sources[0][3:] == (1, 59)


def test_phase2_redacts_provider_messages_and_reports_rate_limits(tmp_path, qapp):
    runtime, db = seeded_runtime(tmp_path)
    with sqlite3.connect(db) as conn:
        conn.execute(
            """INSERT INTO provider_health_state
               (provider,circuit_state,consecutive_failures,updated_at,last_message)
               VALUES (?,?,?,?,?)""",
            ("MASSIVE", "OPEN", 7, "2026-10-08T10:00:00+00:00",
             "API SECRET NEVER DISPLAY ME"),
        )
        conn.execute(
            """INSERT INTO provider_health_events
               (provider,observed_at,success,rate_limited,message)
               VALUES (?,?,?,?,?)""",
            ("MASSIVE", "2026-10-08T10:01:00+00:00", 0, 1,
             "API KEY PRIVATE NEVER DISPLAY ME"),
        )
        conn.execute(
            """INSERT INTO background_sync_tasks
               (task_id,task_type,dedupe_key,status,run_after,created_at,updated_at)
               VALUES ('q1','PIT','job','PENDING',?,?,?)""",
            ("2026-10-08T10:00:00+00:00",) * 3,
        )
    view = DataControlCenterService(runtime_root=runtime).snapshot()
    assert view.phase2.provider_states[0][:3] == ("MASSIVE", "OPEN", 7)
    assert view.phase2.recent_provider_failures[0] == (
        "MASSIVE", "2026-10-08T10:01:00+00:00", True)
    assert view.phase2.queued_tasks == (("PENDING", 1),)
    assert "PRIVATE" not in repr(view.phase2)
    dialog = DataControlCenterDialog(service_factory=None, auto_load=False)
    try:
        dialog.apply_snapshot(view)
        rows = [
            " ".join(dialog.table.item(i, j).text() for j in range(3))
            for i in range(dialog.table.rowCount())
        ]
        rendered = "\n".join(rows)
        assert "API health MASSIVE" in rendered
        assert "Rate limited" in rendered
        assert "API SECRET" not in rendered
        assert "API KEY" not in rendered
        assert "Historical PIT 2014" in rendered
        assert "NO" in rendered
    finally:
        dialog.close()


def test_sec_fact_delta_is_only_manual_observation(tmp_path, qapp):
    from dataclasses import replace
    runtime, _ = seeded_runtime(tmp_path)
    original = DataControlCenterService(runtime_root=runtime).snapshot()
    dialog = DataControlCenterDialog(service_factory=None, auto_load=False)
    try:
        dialog.apply_snapshot(original)
        row1 = next(
            i for i in range(dialog.table.rowCount())
            if dialog.table.item(i, 0).text() == "SEC import progress (manual delta)")
        assert dialog.table.item(row1, 1).text() == "FIRST OBSERVATION"
        dialog.apply_snapshot(replace(original, sec_fact_rows=original.sec_fact_rows + 125))
        row2 = next(
            i for i in range(dialog.table.rowCount())
            if dialog.table.item(i, 0).text() == "SEC import progress (manual delta)")
        assert "+125" in dialog.table.item(row2, 1).text()
        assert "completion" in dialog.table.item(row2, 2).text()
    finally:
        dialog.close()


def test_invalid_wf9_report_never_becomes_success(tmp_path):
    import json
    runtime, _ = seeded_runtime(tmp_path)
    path = runtime / "data/runtime/phase13_readiness/PHASE13_READINESS.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "schema": "WRONG",
        "status": "COMPLETE_AND_ACTIVATED",
        "generated_at": "2026-10-08T10:00:00+00:00",
    }))
    p = DataControlCenterService(runtime_root=runtime).snapshot().phase2
    assert p.wf9_report_status == "INVALID_LOCAL_WF9_REPORT"
    assert p.wf9_report_stale is None


def test_phase2_missing_db_is_nonmutating(tmp_path):
    root = tmp_path / "missing"
    view = DataControlCenterService(runtime_root=root).snapshot()
    assert view.phase2 is not None
    assert view.phase2.sec_archive_status == "SEC_ARCHIVE_NOT_FOUND"
    assert view.phase2.wf9_report_status == "NO_LOCAL_WF9_PREFLIGHT_REPORT"
    assert view.phase2.provider_states == ()
    assert not root.exists()
