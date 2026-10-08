from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path
from scripts.phase13_export_signals import export


def _db(tmp_path: Path, *, state: str = "COMPLETE") -> Path:
    p = tmp_path / "m10.sqlite3"
    con = sqlite3.connect(p)
    con.executescript("""
        CREATE TABLE wf5_replay_runs (
          run_id TEXT PRIMARY KEY, status TEXT,
          start_date TEXT, end_date TEXT
        );
        CREATE TABLE wf5_replay_observations (
          observation_id TEXT, run_id TEXT, security_id TEXT, ticker TEXT,
          as_of_date TEXT, v141_score REAL, v141_status TEXT, outcome_status TEXT
        );
    """)
    con.execute("INSERT INTO wf5_replay_runs VALUES (?,?,?,?)", ("wf5-test", state, "2021-01-01", "2021-12-31"))
    con.executemany("INSERT INTO wf5_replay_observations VALUES (?,?,?,?,?,?,?,?)", [
        ("one", "wf5-test", "SEC-A", "INOD", "2021-01-29", 82.0, "PRECISION_CONFIRMED_12M_10X", "READY"),
        ("two", "wf5-test", "SEC-B", "TMDX", "2021-01-29", None, "INCONCLUSIVE_V1_4_1_INPUTS", "CENSORED"),
    ])
    con.commit()
    con.close()
    return p


def test_phase13_export_validates_and_excludes_inconclusive(tmp_path):
    db = _db(tmp_path)
    result = export(db, "wf5-test", tmp_path / "export")
    assert result["n_source_observations"] == 2
    assert result["n_exported"] == 1
    assert result["pit_verified"] is False
    assert result["excluded"]["MISSING_CANONICAL_SCORE"] == 1
    with (tmp_path / "export/meridyen_signals.csv").open() as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["ticker"] == "INOD"
    assert rows[0]["model_version"] == "S15.3_V1.4.1_CANONICAL_COMPLETION_2026-10-07"
    assert rows[0]["canonical_status"] == "READY"
    assert json.loads((tmp_path / "export/phase13_export_manifest.json").read_text())["status"] == "EXPORT_READY_FOR_INPUT_AUDIT"


def test_phase13_rejects_incomplete_wf5(tmp_path):
    import pytest
    db = _db(tmp_path, state="COMPLETE_WITH_BLOCKERS")
    with pytest.raises(ValueError, match="not COMPLETE"):
        export(db, "wf5-test", tmp_path / "no-export")
    assert not (tmp_path / "no-export").exists()
