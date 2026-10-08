from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import sqlite3

from scripts.phase13_readiness_report import evaluate, write_report, default_db_path


def test_report_missing_database_stays_fail_closed(tmp_path):
    missing = tmp_path / "not-there.db"
    report = evaluate(missing)
    assert report["status"] == "BLOCKED_DB_NOT_FOUND"
    assert report["wf9_activated"] is False
    assert report["pit_independently_verified"] is False
    assert not missing.exists()
    write_report(report, tmp_path / "reports")
    saved = json.loads((tmp_path / "reports/PHASE13_READINESS.json").read_text())
    assert saved["source_class"] == "NO_LOCAL_M10_DB"
    assert "NO_LOCAL_M10_OPERATIONAL_DB" in saved["blockers"]


def test_report_rejects_wrong_sqlite_schema(tmp_path):
    bad = tmp_path / "other.sqlite3"
    sqlite3.connect(bad).close()
    report = evaluate(bad, "2024-01-01", "2024-01-31")
    assert report["status"] == "BLOCKED_SCHEMA"
    assert "wf5_replay_runs" in report["missing_tables"]


def test_report_real_schema_without_data_is_not_success(tmp_path):
    p = tmp_path / "empty_m10.sqlite3"
    conn = sqlite3.connect(p)
    conn.executescript("""
        CREATE TABLE universe_snapshot_membership (snapshot_date TEXT);
        CREATE TABLE canonical_price_selection (id TEXT);
        CREATE TABLE fundamental_facts_source (id TEXT);
        CREATE TABLE canonical_model_features (id TEXT);
        CREATE TABLE wf5_replay_runs (id TEXT);
    """)
    conn.commit()
    conn.close()
    report = evaluate(p, date(2024, 1, 1), date(2024, 1, 31))
    assert report["status"] == "PREFLIGHT_BLOCKED"
    assert report["coverage"]["requested_monthly_dates"] == 1
    assert report["coverage"]["available_monthly_dates"] == 0
    assert "2024-01-31" in report["coverage"]["missing_monthly_dates"]
    assert any("MISSING_PIT_SNAPSHOT_DATES" in x for x in report["blockers"])
    assert report["wf9_activated"] is False


def test_default_runtime_root_can_be_selected_by_env(tmp_path, monkeypatch):
    monkeypatch.setenv("S153_RUNTIME_ROOT", str(tmp_path))
    expected = tmp_path / "data" / "runtime" / "operational.db"
    assert default_db_path() == expected
