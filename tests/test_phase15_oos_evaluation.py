from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import pytest

from scripts.phase15_oos_evaluation import evaluate, _snapshot_metrics


def _sources(tmp_path):
    op=tmp_path/"operational.db"
    le=tmp_path/"learning.sqlite"
    a=sqlite3.connect(op)
    a.executescript("""
      CREATE TABLE wf6_walk_forward_runs
        (run_id TEXT PRIMARY KEY,source_wf5_run_id TEXT,status TEXT);
      CREATE TABLE wf6_walk_forward_folds
        (fold_id TEXT PRIMARY KEY,run_id TEXT,fold_index INTEGER,
         test_start_date TEXT,test_end_date TEXT,status TEXT);
      CREATE TABLE wf6_oos_observations
        (fold_id TEXT,source_observation_id TEXT,security_id TEXT,ticker TEXT,
         as_of_date TEXT,v141_score REAL,v141_status TEXT,outcome_status TEXT,
         fm252 REAL,time_to_2x_sessions INTEGER,time_to_5x_sessions INTEGER,
         time_to_10x_sessions INTEGER);
    """)
    a.execute("INSERT INTO wf6_walk_forward_runs VALUES ('wf6-A','wf5-A','COMPLETE')")
    a.execute("INSERT INTO wf6_walk_forward_folds VALUES ('F1','wf6-A',1,'2020-01-01','2020-12-31','COMPLETE')")
    b=sqlite3.connect(le)
    b.executescript("""
      CREATE TABLE learning_v2_wf5_batches
        (digest TEXT PRIMARY KEY,run_id TEXT,cutoff TEXT,source_pit_verified INTEGER);
      CREATE TABLE learning_v2_wf5_mature_labels
        (digest TEXT,observation_id TEXT,security_id TEXT,ticker TEXT,
         signal_date TEXT,label_available_at TEXT,model_version TEXT,
         canonical_score REAL,horizon_sessions INTEGER,fm252 REAL,
         hit_2x INTEGER,hit_5x INTEGER,hit_10x INTEGER,
         time_to_2x_sessions INTEGER,time_to_5x_sessions INTEGER,
         time_to_10x_sessions INTEGER,outcome_hash TEXT);
    """)
    b.execute("INSERT INTO learning_v2_wf5_batches VALUES ('sha-A','wf5-A','2024-12-31',0)")
    a.commit();b.commit()
    return op,le,a,b


def _row(a,b,symbol,score,multiple,day="2020-01-31",*,label=True,ready=True):
    source_id=f"OBS-{symbol}-{day}"
    security=f"SEC-{symbol}"
    t2=1 if multiple>=2 else None
    t5=2 if multiple>=5 else None
    t10=3 if multiple>=10 else None
    a.execute("""INSERT INTO wf6_oos_observations VALUES
        (?,?,?,?,?,?,?,?,?,?,?,?)""",(
        "F1",source_id,security,symbol,day,score,"10X_DISCOVERY",
        "READY" if ready else "CENSORED",multiple,t2,t5,t10))
    if label:
        b.execute("""INSERT INTO learning_v2_wf5_mature_labels VALUES
         (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(
          "sha-A",source_id,security,symbol,day,"2021-02-01T00:00:00+00:00",
          "S15.3_V1.4.1_CANONICAL_COMPLETION_2026-10-07",score,252,multiple,
          int(multiple>=2),int(multiple>=5),int(multiple>=10),
          t2,t5,t10,"synthetic-hash"))


def _eval(op,le,ks=(2,)):
    return evaluate(op,le,wf6_run_id="wf6-A",batch_sha256="sha-A",
                    cutoff="2026-10-08",ks=ks)


def test_oos_conditional_precision_and_recall_on_complete_snapshot(tmp_path):
    op,le,a,b=_sources(tmp_path)
    _row(a,b,"A",90,12)
    _row(a,b,"B",80,1.5)
    _row(a,b,"C",70,10.2)
    a.commit();b.commit();a.close();b.close()
    r=_eval(op,le,ks=(1,2,3))
    assert r["status"]=="OOS_RESEARCH_DIAGNOSTIC_NOT_PIT_CERTIFIED"
    assert r["fully_labelled_dates"]==1
    assert r["precision_at_k"]["1"]["precision_at_k"]==1.0
    assert r["precision_at_k"]["2"]["precision_at_k"]==0.5
    assert r["precision_at_k"]["2"]["recall_in_evaluated_source_cohort"]==0.5
    assert r["precision_at_k"]["3"]["precision_at_k"]==pytest.approx(2/3)
    assert r["precision_at_k"]["2"]["universe_10x_recall"] is None
    assert r["source_independently_pit_verified"] is False


def test_censored_record_excludes_entire_snapshot_instead_of_selective_win_rate(tmp_path):
    op,le,a,b=_sources(tmp_path)
    _row(a,b,"A",90,10)
    _row(a,b,"B",80,0.2,label=False,ready=False)
    a.commit();b.commit();a.close();b.close()
    r=_eval(op,le)
    assert r["status"]=="BLOCKED_NO_FULLY_MATURE_SNAPSHOT"
    assert r["fully_labelled_dates"]==0
    assert r["precision_at_k"]["2"]["precision_at_k"] is None
    assert r["exclusion_reasons"]["EXCLUDED_INCOMPLETE_SNAPSHOT"]==1


def test_duplicate_security_date_across_oos_folds_is_blocked(tmp_path):
    op,le,a,b=_sources(tmp_path)
    _row(a,b,"A",90,10)
    a.execute("INSERT INTO wf6_walk_forward_folds VALUES ('F2','wf6-A',2,'2020-01-01','2020-12-31','COMPLETE')")
    a.execute("""INSERT INTO wf6_oos_observations
       SELECT 'F2',source_observation_id,security_id,ticker,as_of_date,
       v141_score,v141_status,outcome_status,fm252,time_to_2x_sessions,
       time_to_5x_sessions,time_to_10x_sessions
       FROM wf6_oos_observations""")
    a.commit();b.commit();a.close();b.close()
    with pytest.raises(ValueError,match="Overlapping folds"):
        _eval(op,le,ks=(1,))


def test_frozen_scores_must_match_source_evidence(tmp_path):
    op,le,a,b=_sources(tmp_path)
    _row(a,b,"A",90,10)
    b.execute("UPDATE learning_v2_wf5_mature_labels SET canonical_score=40")
    a.commit();b.commit();a.close();b.close()
    with pytest.raises(ValueError,match="score differs"):
        _eval(op,le,ks=(1,))


def test_maturity_cutoff_rejects_future_known_labels(tmp_path):
    op,le,a,b=_sources(tmp_path)
    _row(a,b,"A",90,10)
    b.execute("UPDATE learning_v2_wf5_mature_labels SET label_available_at='2027-01-01T00:00:00+00:00'")
    a.commit();b.commit();a.close();b.close()
    r=_eval(op,le,ks=(1,))
    assert r["fully_labelled_dates"]==0


def test_source_batch_has_to_match_wf6(tmp_path):
    op,le,a,b=_sources(tmp_path)
    b.execute("UPDATE learning_v2_wf5_batches SET run_id='other-wf5'")
    a.commit();b.commit();a.close();b.close()
    with pytest.raises(ValueError,match="must match"):
        _eval(op,le,ks=(1,))


def test_precision_denominators_and_undefined_recall(tmp_path):
    x=_snapshot_metrics([
        {"security_id":"AA","ticker":"A","score":90,"hit10":0},
        {"security_id":"BB","ticker":"B","score":80,"hit10":0},
    ],(1,2,10))
    assert x["cohort_base_rate_10x"]==0
    assert x["at_k"]["2"]["recall_within_source_cohort"] is None
    assert x["at_k"]["10"]["status"]=="INSUFFICIENT_COHORT"
