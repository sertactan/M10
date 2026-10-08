import json
import sqlite3
from pathlib import Path
import pytest
from scripts.phase17_export_features import export
from scripts.phase17_improve_plan import plan

def build_sources(tmp_path):
    op=tmp_path/"op.sqlite3"; le=tmp_path/"learning.sqlite3"
    a=sqlite3.connect(op)
    a.executescript("""
    CREATE TABLE wf5_replay_runs(run_id TEXT,status TEXT);
    CREATE TABLE wf5_replay_observations(
       observation_id TEXT,run_id TEXT,security_id TEXT,ticker TEXT,
       as_of_date TEXT,v141_score REAL,v141_status TEXT,outcome_status TEXT);
    CREATE TABLE canonical_model_features(
       security_id TEXT,feature_key TEXT,value REAL,feature_as_of TEXT,
       available_at TEXT,source_phase TEXT,source_ref TEXT,quality_status TEXT);
    """)
    a.execute("INSERT INTO wf5_replay_runs VALUES ('WF5','COMPLETE')")
    b=sqlite3.connect(le)
    b.executescript("""
    CREATE TABLE learning_v2_wf5_batches(digest TEXT,run_id TEXT,cutoff TEXT);
    CREATE TABLE learning_v2_wf5_mature_labels(
       security_id TEXT,signal_date TEXT,digest TEXT,observation_id TEXT,
       label_available_at TEXT,model_version TEXT,canonical_score REAL,
       hit_10x INTEGER,outcome_hash TEXT);
    """)
    b.execute("INSERT INTO learning_v2_wf5_batches VALUES ('hash','WF5','2025-01-01')")
    for day in ("2020-01-31","2021-01-29"):
        for idx in range(2):
            sec=f"SEC-{day}-{idx}"
            ident=f"OBS-{sec}"
            a.execute("INSERT INTO wf5_replay_observations VALUES (?,?,?,?,?,?,?,?)",
               (ident,"WF5",sec,"TEST",day,80.0,"10X_DISCOVERY","READY"))
            a.execute("INSERT INTO canonical_model_features VALUES (?,?,?,?,?,?,?,?)",
               (sec,"D01",float(50+idx),day+"T16:00:00+00:00",day+"T15:00:00+00:00",
                "PHASE3_FUNDAMENTAL","SEC-primary-document","VALIDATED"))
            b.execute("INSERT INTO learning_v2_wf5_mature_labels VALUES (?,?,?,?,?,?,?,?,?)",
               (sec,day,"hash",ident,"2023-01-01T00:00:00+00:00",
                "S15.3_V1.4.1_CANONICAL_COMPLETION_2026-10-07",80.0,idx==0,"a"*64))
    a.commit();b.commit();a.close();b.close()
    return op,le

def export_it(op,le):
    return export(op,le,wf5_run_id="WF5",batch_sha256="hash",features=["D01"],cutoff="2026-10-08")

def test_complete_wf5_feature_cohorts_exported(tmp_path):
    op,le=build_sources(tmp_path)
    result=export_it(op,le)
    assert len(result["rows"])==4
    assert result["schema"]=="MERIDYEN_V3_DATED_COHORT_V1"
    assert all(r["snapshot_expected_count"]==2 for r in result["rows"])
    assert result["source_data_pit_independently_certified"] is False

def test_missing_feature_excludes_full_date(tmp_path):
    op,le=build_sources(tmp_path)
    a=sqlite3.connect(op)
    a.execute("DELETE FROM canonical_model_features WHERE security_id=?",
              ("SEC-2020-01-31-0",))
    a.commit();a.close()
    result=export_it(op,le)
    assert len(result["rows"])==2
    assert result["omitted_dates"]["INCOMPLETE_COHORT_DATE"]==1

def test_late_feature_cannot_enter_historical_snapshot(tmp_path):
    op,le=build_sources(tmp_path)
    a=sqlite3.connect(op)
    a.execute("UPDATE canonical_model_features SET available_at=? WHERE security_id=?",
              ("2025-01-01T00:00:00+00:00","SEC-2020-01-31-0"))
    a.commit();a.close()
    assert len(export_it(op,le)["rows"])==2

def test_late_label_or_incomplete_source_does_not_inflate_sample(tmp_path):
    op,le=build_sources(tmp_path)
    b=sqlite3.connect(le)
    b.execute("UPDATE learning_v2_wf5_mature_labels SET label_available_at=? WHERE signal_date=?",
              ("2030-01-01T00:00:00+00:00","2020-01-31"))
    b.commit();b.close()
    assert len(export_it(op,le)["rows"])==2

def test_governance_planner_blocks_promotions_and_has_backlog():
    p=plan()
    assert p["auto_merge"] is False
    assert p["approved_model_promotion"] is False
    assert p["issues"][0]["priority"]=="P0"
    good={"schema":"MERIDYEN_LEARNING_V3_EXPERIMENT_V1",
          "production_promotion_allowed":False,
          "metrics":{"precision_delta_pp":12.5}}
    other=plan(experiment_report=good)
    assert any(i["code"]=="CHALLENGER_NEEDS_INDEPENDENT_REPLICATION" for i in other["issues"])
    with pytest.raises(ValueError,match="Unsafe challenger"):
        plan(experiment_report={**good,"production_promotion_allowed":True})
