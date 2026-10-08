from __future__ import annotations

from datetime import date, timedelta, datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import pytest

from core.learning_v2.wf5_outcome_bridge import ingest_wf5, audit_wf5_learning


def _sample(tmp_path, *, run_status="COMPLETE"):
    db=tmp_path/"operational.db"
    conn=sqlite3.connect(db)
    conn.executescript("""
    CREATE TABLE wf5_replay_runs (run_id TEXT PRIMARY KEY,status TEXT);
    CREATE TABLE wf5_replay_observations (
      observation_id TEXT PRIMARY KEY,run_id TEXT,security_id TEXT,
      ticker TEXT,as_of_date TEXT,v141_score REAL,v141_status TEXT,
      outcome_status TEXT
    );
    CREATE TABLE forward_outcomes (
      observation_id TEXT PRIMARY KEY,security_id TEXT,as_of_date_requested TEXT,
      anchor_session TEXT,anchor_lag_calendar_days INTEGER,entry_adjusted_close REAL,
      horizon_sessions_available INTEGER,fm252 REAL,max_multiple_observed REAL,
      outcome_class TEXT,time_to_2x_sessions INTEGER,time_to_3x_sessions INTEGER,
      time_to_5x_sessions INTEGER,time_to_7x_sessions INTEGER,time_to_10x_sessions INTEGER,
      outcome_status TEXT,diagnostics_json TEXT,outcome_hash TEXT
    );
    CREATE TABLE s153_historical_control_observations (
      observation_id TEXT PRIMARY KEY,security_id TEXT,as_of_date TEXT,
      source_run_id TEXT,label_available_at TEXT,fm252 REAL,outcome_class TEXT
    );
    """)
    conn.execute("INSERT INTO wf5_replay_runs VALUES (?,?)",("run1",run_status))
    conn.commit()
    conn.close()
    return db


def _put(conn, ticker, security, stamp, multiple, *, label_date="2025-01-02T23:59:59+00:00",
         ready=True, hash_valid=True, cohort=True, points=252, override_class=None, terminal=False):
    obs=f"wf5-{security}-{stamp}"
    cls=override_class or ("TRUE_10X" if multiple>=10 else "MODERATE_WINNER" if multiple>=2 else "FAILURE")
    conn.execute("INSERT INTO wf5_replay_observations VALUES (?,?,?,?,?,?,?,?)",(
        obs,"run1",security,ticker,stamp,85.0,
        "PRECISION_CONFIRMED_12M_10X","READY" if ready else "CENSORED"))
    if not ready:
        return
    forward_id=f"{security}|{stamp}"
    ti=lambda multiple_: 1 if multiple>=multiple_ and not terminal else None
    payload=dict(
        observation_id=forward_id,security_id=security,as_of_date_requested=stamp,
        anchor_session=stamp,anchor_lag_calendar_days=0,entry_adjusted_close=10.0,
        horizon_sessions_available=points,fm252=float(multiple),
        max_multiple_observed=float(multiple),outcome_class=cls,
        time_to_2x_sessions=ti(2),time_to_3x_sessions=ti(3),
        time_to_5x_sessions=ti(5),time_to_7x_sessions=ti(7),
        time_to_10x_sessions=ti(10),outcome_status="READY",
        diagnostics={"source":"SYNTHETIC_FIXTURE","terminal_consideration_used":terminal,
                     "terminal_horizon_verified":terminal,
                     "terminal_source_ref":"synthetic-primary-source" if terminal else None})
    checksum=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()
    if not hash_valid:
        checksum="a"*64
    conn.execute("INSERT INTO forward_outcomes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(
        forward_id,security,stamp,stamp,0,10.0,points,float(multiple),float(multiple),
        cls,ti(2),ti(3),ti(5),ti(7),ti(10),"READY",
        json.dumps(payload["diagnostics"]),checksum))
    if cohort:
        conn.execute("INSERT INTO s153_historical_control_observations VALUES (?,?,?,?,?,?,?)",(
            forward_id,security,stamp,"run1",label_date,float(multiple),cls))


def test_mature_2x_and_10x_are_imported_without_double_count(tmp_path):
    src=_sample(tmp_path)
    c=sqlite3.connect(src)
    _put(c,"INOD","SEC-A","2024-01-02",10.3)
    _put(c,"TMDX","SEC-B","2024-01-02",2.2)
    _put(c,"CRMD","SEC-C","2024-01-02",11.2,label_date="2027-01-02T23:59:59+00:00")
    _put(c,"FAIL","SEC-D","2024-01-02",.4,ready=False)
    c.commit();c.close()
    learn=tmp_path/"private-learning.sqlite3"
    res=ingest_wf5(src,learn,run_id="run1",cutoff="2026-10-08")
    assert res["status"]=="MATURE_WF5_EVIDENCE_IMPORTED"
    assert (res["n_mature"],res["n_censored"])==(2,2)
    assert (res["hits_2x"],res["hits_5x"],res["hits_10x"])==(2,1,1)
    assert res["source_pit_independently_verified"] is False
    res2=ingest_wf5(src,learn,run_id="run1",cutoff="2026-10-08")
    assert res2["status"]=="DUPLICATE"
    aud=audit_wf5_learning(learn)
    assert aud["observations_including_snapshot_versions"]==2
    c=sqlite3.connect(learn)
    assert c.execute("SELECT COUNT(*) FROM learning_v2_outcomes").fetchone()[0]==0
    assert c.execute("SELECT COUNT(*) FROM learning_v2_wf5_mature_labels").fetchone()[0]==2
    c.close()


def test_outcome_hash_tamper_blocked_before_learning_db_created(tmp_path):
    db=_sample(tmp_path)
    c=sqlite3.connect(db)
    _put(c,"INOD","SEC-A","2024-01-02",10.1,hash_valid=False)
    c.commit();c.close()
    learning=tmp_path/"learning.sqlite3"
    with pytest.raises(ValueError,match="hash mismatch"):
        ingest_wf5(db,learning,run_id="run1",cutoff="2026-10-08")
    assert not learning.exists()


def test_incomplete_run_rejected(tmp_path):
    db=_sample(tmp_path,run_status="COMPLETE_WITH_BLOCKERS")
    with pytest.raises(ValueError,match="COMPLETE"):
        ingest_wf5(db,tmp_path/"learning.sqlite3",run_id="run1",cutoff="2026-10-08")


def test_censored_only_never_creates_false_success(tmp_path):
    db=_sample(tmp_path)
    c=sqlite3.connect(db)
    _put(c,"CRMD","SEC-C","2024-01-02",10.0,label_date="2028-01-02T23:59:59+00:00")
    c.commit();c.close()
    learning=tmp_path/"learning.sqlite3"
    with pytest.raises(ValueError,match="No verifiably mature"):
        ingest_wf5(db,learning,run_id="run1",cutoff="2026-10-08")
    assert not learning.exists()


def test_cohort_mismatch_is_censored_not_positive(tmp_path):
    db=_sample(tmp_path)
    c=sqlite3.connect(db)
    _put(c,"INOD","SEC-A","2024-01-02",10.0,cohort=False)
    c.commit();c.close()
    with pytest.raises(ValueError,match="No verifiably mature"):
        ingest_wf5(db,tmp_path/"learning.sqlite3",run_id="run1",cutoff="2026-10-08")


def test_short_251_session_path_does_not_become_mature_label(tmp_path):
    db=_sample(tmp_path)
    c=sqlite3.connect(db)
    _put(c,"CRMD","SEC-C","2024-01-02",10.0,points=251)
    c.commit();c.close()
    with pytest.raises(ValueError,match="No verifiably mature"):
        ingest_wf5(db,tmp_path/"learning.sqlite3",run_id="run1",cutoff="2026-10-08")


def test_reject_future_cutoff_without_database_creation(tmp_path):
    db=_sample(tmp_path)
    with pytest.raises(ValueError,match="future"):
        ingest_wf5(db,tmp_path/"learning.sqlite3",run_id="run1",cutoff="2099-01-01")


def test_source_db_same_as_learning_db_refused(tmp_path):
    db=_sample(tmp_path)
    with pytest.raises(ValueError,match="distinct"):
        ingest_wf5(db,db,run_id="run1",cutoff="2026-10-08")



def test_verified_terminal_consideration_allows_short_horizon_without_invented_hit_time(tmp_path):
    db=_sample(tmp_path)
    c=sqlite3.connect(db)
    _put(c,"DELISTED","SEC-DEL","2024-01-02",11.0,points=63,terminal=True)
    c.commit();c.close()
    out=ingest_wf5(db,tmp_path/"learning.sqlite3",run_id="run1",cutoff="2026-10-08")
    assert out["n_mature"]==1
    assert out["hits_10x"]==1
    learned=sqlite3.connect(tmp_path/"learning.sqlite3")
    assert learned.execute("SELECT time_to_10x_sessions FROM learning_v2_wf5_mature_labels").fetchone()[0] is None
    learned.close()
