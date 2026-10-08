from __future__ import annotations

"""Learning V2's native WF5 outcome maturity bridge.

Read a *completed* WF5 PIT replay from operational.db, join ONLY source
documented 252-session terminal labels, then append an immutable research
outcome snapshot to a separate Learning V2 SQLite file. No scoring,
price fetching, re-training or trade execution. This is not proof of
independently audited full-US PIT data coverage.
"""

from datetime import date, datetime, time, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3

from core.learning_v2.journal import connect

ENGINE = "MERIDYEN_LEARNING_V2_WF5_OUTCOMES_V1"
VERSION = "S15.3_V1.4.1_CANONICAL_COMPLETION_2026-10-07"
REQUIRED = ("wf5_replay_runs", "wf5_replay_observations", "forward_outcomes",
            "s153_historical_control_observations")
READY_STATUSES = {
    "PRECISION_CONFIRMED_12M_10X", "HIGH_SCORE_NOT_CONFIRMED",
    "STRONG_10X_WATCH", "10X_DISCOVERY", "NO_CANONICAL_GATE_STATUS",
    "EARLY_ASYMMETRIC", "EARLY_ASYMMETRIC_WATCH",
}


def _canonical_json(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _date(value, name):
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name}: ISO date required") from exc


def _label_time(value):
    try:
        dt = datetime.fromisoformat(str(value))
        if dt.tzinfo is None:
            raise ValueError("timezone required")
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid label_available_at UTC timestamp") from exc


def _forward_payload(row):
    """Mirror BacktestRepository.save_forward_outcome's hashed fields."""
    names = (
        "observation_id", "security_id", "as_of_date_requested",
        "anchor_session", "anchor_lag_calendar_days", "entry_adjusted_close",
        "horizon_sessions_available", "fm252", "max_multiple_observed",
        "outcome_class", "time_to_2x_sessions", "time_to_3x_sessions",
        "time_to_5x_sessions", "time_to_7x_sessions",
        "time_to_10x_sessions", "outcome_status",
    )
    data = {k: row[k] for k in names}
    data["diagnostics"] = json.loads(row["diagnostics_json"])
    return data


def _assert_outcome_hash(row):
    payload = _forward_payload(row)
    actual = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    if actual != row["outcome_hash"]:
        raise ValueError(f"Source forward-outcome hash mismatch: {row['observation_id']}")
    return actual


def _qualified(row, cutoff):
    """Return a mature, evidence-linked outcome or an explicit censored reason."""
    if row["v141_score"] is None:
        return None, "NO_S15_CANONICAL_SCORE"
    score = float(row["v141_score"])
    if not math.isfinite(score) or not 0 <= score <= 100:
        raise ValueError("Invalid S15 canonical score")
    if row["v141_status"] not in READY_STATUSES:
        return None, "UNRECOGNIZED_OR_INCONCLUSIVE_S15_STATUS"
    if row["outcome_status"] != "READY" or row["f_observation_id"] is None:
        return None, "CENSORED_OR_MISSING_OUTCOME"

    outcome = row["f_status"]
    if outcome != "READY":
        return None, "CENSORED_FORWARD_LABEL"
    if int(row["horizon_sessions_available"]) < 252:
        return None, "CENSORED_SHORT_PRICE_SERIES"
    if row["label_available_at"] is None:
        return None, "CENSORED_MISSING_LABEL_DATE"
    date_of_label = _label_time(row["label_available_at"])
    signal = _date(row["as_of_date"], "signal")
    if date_of_label.date() <= signal:
        raise ValueError("label_available_at must follow signal date")
    if date_of_label > datetime.combine(cutoff,time.max,tzinfo=timezone.utc):
        return None, "CENSORED_LABEL_NOT_YET_MATURE"
    if row["control_run_id"] != row["run_id"]:
        return None, "CENSORED_LABEL_SOURCE_RUN_MISMATCH"
    if row["f_security_id"] != row["security_id"] or row["f_as_of"] != row["as_of_date"]:
        raise ValueError("Forward outcome identity mismatch")
    if row["anchor_session"] is None or _date(row["anchor_session"],"anchor") > signal:
        raise ValueError("Invalid anchor session")
    x = float(row["fm252"])
    cx = float(row["control_fm252"])
    if not math.isfinite(x) or x < 0 or not math.isfinite(cx) or abs(x-cx)>1e-8:
        raise ValueError("Canonical 252-session outcome does not tie to cohort")
    for key,threshold in (("time_to_2x_sessions",2),("time_to_5x_sessions",5),("time_to_10x_sessions",10)):
        t=row[key]
        if t is not None and (not 1 <= int(t) <= 252 or int(t)!=t):
            raise ValueError(f"Invalid {key} index")
        if bool(t is not None) != (x >= threshold):
            raise ValueError(f"{key} incompatible with fm252")
    _assert_outcome_hash(row)
    if row["outcome_class"] != row["control_outcome_class"]:
        raise ValueError("Forward cohort outcome class mismatch")
    return {
        "ticker": row["ticker"],
        "security_id": row["security_id"],
        "signal_date": row["as_of_date"],
        "model_version": VERSION,
        "canonical_score": score,
        "label_available_at": date_of_label.isoformat(),
        "horizon_sessions": 252,
        "fm252": x,
        "hit_2x": bool(x >= 2.0),
        "hit_5x": bool(x >= 5.0),
        "hit_10x": bool(x >= 10.0),
        "time_to_2x_sessions": row["time_to_2x_sessions"],
        "time_to_5x_sessions": row["time_to_5x_sessions"],
        "time_to_10x_sessions": row["time_to_10x_sessions"],
        "outcome_hash": row["outcome_hash"],
        "observation_id": row["observation_id"],
    }, "MATURE"


def _load_rows(db, run_id):
    source = sqlite3.connect(Path(db).resolve().as_uri()+"?mode=ro",uri=True)
    source.row_factory = sqlite3.Row
    try:
        present={r[0] for r in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        absent=sorted(set(REQUIRED)-present)
        if absent:
            raise ValueError("Missing canonical PIT tables: "+", ".join(absent))
        run=source.execute("SELECT status FROM wf5_replay_runs WHERE run_id=?", (run_id,)).fetchone()
        if run is None or run["status"]!="COMPLETE":
            raise ValueError("WF5 run must exist and be COMPLETE")
        rows=source.execute("""
            SELECT o.*, f.observation_id AS f_observation_id,
                   f.security_id AS f_security_id,
                   f.as_of_date_requested AS f_as_of,
                   f.horizon_sessions_available, f.fm252, f.outcome_class,
                   f.outcome_status AS f_status, f.outcome_hash,
                   f.diagnostics_json, f.anchor_session,
                   f.anchor_lag_calendar_days, f.entry_adjusted_close,
                   f.max_multiple_observed,
                   f.time_to_2x_sessions, f.time_to_3x_sessions,
                   f.time_to_5x_sessions, f.time_to_7x_sessions,
                   f.time_to_10x_sessions,
                   h.label_available_at, h.source_run_id AS control_run_id,
                   h.fm252 AS control_fm252,
                   h.outcome_class AS control_outcome_class
            FROM wf5_replay_observations o
            LEFT JOIN forward_outcomes f
             ON f.security_id=o.security_id
            AND f.as_of_date_requested=o.as_of_date
            LEFT JOIN s153_historical_control_observations h
             ON h.security_id=o.security_id
            AND h.as_of_date=o.as_of_date
            AND h.source_run_id=o.run_id
            WHERE o.run_id=?
            ORDER BY o.as_of_date, o.security_id
        """,(run_id,)).fetchall()
    finally:
        source.close()
    if not rows:
        raise ValueError("Completed WF5 run has no observations")
    found=set()
    for row in rows:
        ident=(row["security_id"],row["as_of_date"])
        if ident in found:
            raise ValueError("Duplicated WF5 observation or historical cohort")
        found.add(ident)
    return rows


def ingest_wf5(operational_db, learning_db, *, run_id, cutoff):
    """Atomic, deduplicated append of *mature* outcomes to local Learning V2.

    The cutoff represents end-of-day knowledge, not a future backtest score date.
    Censored, inconclusive, and insufficient-provenance rows stay separate.
    """
    cutoff=_date(cutoff, "cutoff")
    if cutoff>date.today():
        raise ValueError("cutoff cannot be in the future")
    if Path(operational_db).resolve()==Path(learning_db).resolve():
        raise ValueError("Learning and operational DB must be distinct")
    if not Path(operational_db).is_file():
        raise ValueError("Missing native M10 operational.db")
    rows=_load_rows(operational_db, run_id)
    outcomes=[];censored={}
    for row in rows:
        result,status=_qualified(row,cutoff)
        if result is None:
            censored[status]=censored.get(status,0)+1
        else:
            outcomes.append(result)
    if not outcomes:
        raise ValueError("No verifiably mature, source-linked WF5 outcome; no label import")
    digest=hashlib.sha256(_canonical_json({
        "schema":ENGINE, "run_id":run_id,"cutoff":cutoff.isoformat(),
        "data":outcomes,
    }).encode("utf-8")).hexdigest()
    conn=connect(learning_db)
    try:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS learning_v2_wf5_batches (
          digest TEXT PRIMARY KEY, run_id TEXT NOT NULL, cutoff TEXT NOT NULL,
          imported_at TEXT NOT NULL, mature_count INTEGER NOT NULL,
          censored_counts_json TEXT NOT NULL,
          source_pit_verified INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS learning_v2_wf5_mature_labels (
          digest TEXT NOT NULL REFERENCES learning_v2_wf5_batches(digest),
          observation_id TEXT NOT NULL, security_id TEXT NOT NULL, ticker TEXT NOT NULL,
          signal_date TEXT NOT NULL, label_available_at TEXT NOT NULL,
          model_version TEXT NOT NULL, canonical_score REAL NOT NULL,
          horizon_sessions INTEGER NOT NULL, fm252 REAL NOT NULL,
          hit_2x INTEGER NOT NULL, hit_5x INTEGER NOT NULL, hit_10x INTEGER NOT NULL,
          time_to_2x_sessions INTEGER, time_to_5x_sessions INTEGER,
          time_to_10x_sessions INTEGER, outcome_hash TEXT NOT NULL,
          PRIMARY KEY(digest, observation_id)
        );
        """)
        existing=conn.execute("SELECT mature_count FROM learning_v2_wf5_batches WHERE digest=?",(digest,)).fetchone()
        if existing:
            n=conn.execute("SELECT COUNT(*) FROM learning_v2_wf5_mature_labels WHERE digest=?",(digest,)).fetchone()[0]
            if n!=existing[0] or n!=len(outcomes):
                raise ValueError("Existing WF5 batch evidence partially missing")
        else:
            with conn:
                conn.execute("""INSERT INTO learning_v2_wf5_batches
                  (digest,run_id,cutoff,imported_at,mature_count,censored_counts_json,source_pit_verified)
                  VALUES (?,?,?,?,?,?,0)""",
                  (digest,run_id,cutoff.isoformat(),datetime.now(timezone.utc).isoformat(),
                   len(outcomes),_canonical_json(censored)))
                conn.executemany("""INSERT INTO learning_v2_wf5_mature_labels
                  (digest,observation_id,security_id,ticker,signal_date,
                   label_available_at,model_version,canonical_score,horizon_sessions,
                   fm252,hit_2x,hit_5x,hit_10x,time_to_2x_sessions,
                   time_to_5x_sessions,time_to_10x_sessions,outcome_hash)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",[
                    (digest,r["observation_id"],r["security_id"],r["ticker"],
                     r["signal_date"],r["label_available_at"],r["model_version"],
                     r["canonical_score"],r["horizon_sessions"],r["fm252"],
                     int(r["hit_2x"]),int(r["hit_5x"]),int(r["hit_10x"]),
                     r["time_to_2x_sessions"],r["time_to_5x_sessions"],
                     r["time_to_10x_sessions"],r["outcome_hash"])
                    for r in outcomes])
    finally:
        conn.close()
    n=len(outcomes)
    return {
        "status":"DUPLICATE" if existing else "MATURE_WF5_EVIDENCE_IMPORTED",
        "engine":ENGINE,"run_id":run_id,"as_of":cutoff.isoformat(),
        "batch_sha256":digest, "n_mature":n, "n_censored":len(rows)-n,
        "censored_reasons":censored,
        "hits_2x":sum(r["hit_2x"] for r in outcomes),
        "hits_5x":sum(r["hit_5x"] for r in outcomes),
        "hits_10x":sum(r["hit_10x"] for r in outcomes),
        "source_pit_independently_verified":False,
        "model_training_performed":False,
        "canonical_s15_s16_unchanged":True,
        "warning":"Conditional hit counts among available mature outcomes, NOT whole-US 10X recall or OOS performance.",
    }


def audit_wf5_learning(learning_db):
    conn=connect(learning_db)
    try:
        exists=conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='learning_v2_wf5_batches'").fetchone()
        if not exists:
            return {"status":"NO_WF5_EVIDENCE","batches":0,"observations":0}
        q=conn.execute("""SELECT COUNT(*),COALESCE(SUM(hit_2x),0),COALESCE(SUM(hit_5x),0),
                          COALESCE(SUM(hit_10x),0) FROM learning_v2_wf5_mature_labels""").fetchone()
        count=conn.execute("SELECT COUNT(*) FROM learning_v2_wf5_batches").fetchone()[0]
        return {"status":"RESEARCH_WF5_EVIDENCE_ONLY", "batches":count,
                "observations_including_snapshot_versions":q[0],
                "hits_2x":q[1],"hits_5x":q[2],"hits_10x":q[3],
                "warning":"Do not aggregate multiple batch revisions as independent observations.",
                "source_pit_certified":False,"trained":False}
    finally:
        conn.close()
