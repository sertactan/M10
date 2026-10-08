from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
from zipfile import ZipFile

import pytest
from scripts.import_research_pilot import import_pilot, inspect_pilot, audit_research


def _pilot(tmp_path: Path, *, status="CALCULATED_NONCANONICAL"):
    d = tmp_path / "source"
    (d / "results").mkdir(parents=True)
    result = {"ticker": "INOD", "mode": "inflection", "as_of": "2026-10-08",
              "status": "NONCANONICAL_RESEARCH_ONLY",
              "pit_certified": False, "ranked": [{"metric": "revenue",
                                                 "acceleration": 0.3}]}
    if status == "BLOCKED_INSUFFICIENT_DATA":
        result = {"ticker": "INOD", "mode": "dcf", "as_of": "2026-10-08",
                  "error_type": "ValueError", "error": "Missing WACC",
                  "pit_certified": False}
    name = f"results/INOD_{result['mode']}.json"
    raw = (json.dumps(result) + "\n").encode("utf-8")
    (d / name).write_bytes(raw)
    manifest = {"metadata": {
        "schema": "MERIDYEN_REAL_SEC_PILOT_V1",
        "as_of": "2026-10-08",
        "pit_certified": False,
        "is_historical_backtest": False,
        "mature_outcomes": 0, "canonical_signal_count": 0,
        "source_urls": {"INOD": {"q2":
            "https://www.sec.gov/Archives/edgar/data/903651/some-10q"}},
    }, "runs": [{"ticker": "INOD", "mode": result["mode"], "status": status,
                   "result_path": name,
                   "result_sha256": hashlib.sha256(raw).hexdigest()}]}
    (d / "run_manifest.json").write_text(json.dumps(manifest) + "\n")
    return d


def test_import_research_only_append_and_duplicate(tmp_path):
    src = _pilot(tmp_path)
    db = tmp_path / "learning.sqlite3"
    first = import_pilot(db, src)
    second = import_pilot(db, src)
    assert first["status"] == "RESEARCH_IMPORTED"
    assert second["status"] == "DUPLICATE"
    assert first["research_routes"] == 1
    assert first["mature_outcomes_imported"] == 0
    assert first["canonical_scores_updated"] == 0
    state = audit_research(db)
    assert state["research_sources"] == 1
    assert state["route_statuses"]["CALCULATED_NONCANONICAL"] == 1
    con = sqlite3.connect(db)
    # Existing v2 mature outcomes are NOT populated by these research observations.
    assert con.execute("SELECT COUNT(*) FROM learning_v2_outcomes").fetchone()[0] == 0
    assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    con.close()


def test_import_from_zip(tmp_path):
    src = _pilot(tmp_path)
    zip_path = tmp_path / "pilot.zip"
    with ZipFile(zip_path, "w") as archive:
        for file in src.rglob("*"):
            if file.is_file():
                archive.write(file, file.relative_to(src).as_posix())
    out = import_pilot(tmp_path / "learning.sqlite3", zip_path)
    assert out["status"] == "RESEARCH_IMPORTED"
    assert out["tickers"] == 1


def test_corrupt_result_hash_fails_before_db_creation(tmp_path):
    src = _pilot(tmp_path)
    result = next((src / "results").glob("*.json"))
    result.write_text('{"ticker":"INOD","mode":"inflection","as_of":"2026-10-08"}')
    db = tmp_path / "new.sqlite3"
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        import_pilot(db, src)
    assert not db.exists()


def test_rejects_model_outcomes_and_pit_claims(tmp_path):
    src = _pilot(tmp_path)
    manifest = src / "run_manifest.json"
    for key, value in (("mature_outcomes", 1), ("pit_certified", True),
                       ("is_historical_backtest", True), ("canonical_signal_count", 1)):
        obj = json.loads(manifest.read_text())
        obj["metadata"][key] = value
        manifest.write_text(json.dumps(obj))
        with pytest.raises(ValueError, match="cannot|non-PIT"):
            inspect_pilot(src)
        obj["metadata"][key] = {"mature_outcomes":0,"pit_certified":False,
                                "is_historical_backtest":False,
                                "canonical_signal_count":0}[key]
        manifest.write_text(json.dumps(obj))


def test_blocked_mode_can_be_archived_but_not_training_data(tmp_path):
    src = _pilot(tmp_path, status="BLOCKED_INSUFFICIENT_DATA")
    db = tmp_path / "learning.sqlite3"
    result = import_pilot(db, src)
    assert result["research_routes"] == 1
    assert audit_research(db)["route_statuses"] == {"BLOCKED_INSUFFICIENT_DATA": 1}
    con = sqlite3.connect(db)
    assert con.execute("SELECT COUNT(*) FROM learning_v2_outcomes").fetchone()[0] == 0
    con.close()


def test_unsafe_manifest_paths_rejected(tmp_path):
    src = _pilot(tmp_path)
    man = src / "run_manifest.json"
    obj = json.loads(man.read_text())
    obj["runs"][0]["result_path"] = "../private.json"
    man.write_text(json.dumps(obj))
    with pytest.raises(ValueError, match="Unsafe"):
        inspect_pilot(src)


def test_unknown_status_rejected(tmp_path):
    src = _pilot(tmp_path)
    man = src / "run_manifest.json"
    obj = json.loads(man.read_text())
    obj["runs"][0]["status"] = "CANONICAL_READY"
    man.write_text(json.dumps(obj))
    with pytest.raises(ValueError, match="unknown"):
        inspect_pilot(src)
