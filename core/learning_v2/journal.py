from __future__ import annotations

"""Meridyen V2 local-first, append-only learning journal.

No model-weight updates. Designed for a *private* SQLite file on M10's
writable runtime volume; only metadata/manifests belong in public GitHub.
"""
import hashlib
import json
import math
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

ENGINE = "MERIDYEN_LEARNING_V2"
SCHEMA_VERSION = 1


def _iso(value, field):
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        raise ValueError(f"invalid {field}: {value}")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def connect(db_path):
    p = Path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS learning_v2_sources (
      id INTEGER PRIMARY KEY, sha256 TEXT NOT NULL UNIQUE,
      kind TEXT NOT NULL, imported_at TEXT NOT NULL,
      as_of TEXT NOT NULL, n_total INTEGER NOT NULL,
      n_complete INTEGER NOT NULL, claimed_pit INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS learning_v2_outcomes (
      id INTEGER PRIMARY KEY, source_id INTEGER NOT NULL
       REFERENCES learning_v2_sources(id),
      source_ordinal INTEGER NOT NULL, ticker TEXT NOT NULL,
      signal_date TEXT NOT NULL, source_as_of TEXT NOT NULL,
      model_version TEXT NOT NULL, horizon_sessions INTEGER NOT NULL,
      completed INTEGER NOT NULL, terminal_return REAL,
      hit_10x INTEGER, provenance TEXT NOT NULL,
      UNIQUE(source_id,source_ordinal)
    );
    CREATE TABLE IF NOT EXISTS learning_v2_feedback (
      id INTEGER PRIMARY KEY, category TEXT NOT NULL,
      note TEXT NOT NULL, source_ref TEXT NOT NULL,
      created_at TEXT NOT NULL
    );
    """)
    return conn


def learn_backtest(db_path, path, as_of):
    """Load a dated v0.12 event study, deduplicated by SHA256.

    Input PIT is not independently certified. Censored rows aren't failures.
    No private data is uploaded to GitHub or Drive automatically.
    """
    asof = _iso(as_of, "as_of")
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    meta, events = data.get("metadata"), data.get("events")
    if not isinstance(meta, dict) or not isinstance(events, list) or not events:
        raise ValueError("backtest.json must contain metadata and nonempty events")
    source_asof = _iso(meta.get("as_of"), "metadata.as_of")
    if source_asof > asof:
        raise ValueError("backtest source generated in the future")
    rows = []
    for i, e in enumerate(events):
        ticker = str(e.get("ticker") or "").strip().upper()
        version = str(e.get("model_version") or "").strip()
        signal = _iso(e.get("signal_date"), f"event[{i}].signal_date")
        source = _iso(e.get("source_as_of"), f"event[{i}].source_as_of")
        horizon = int(e.get("horizon_sessions") or 0)
        completed = e.get("completed")
        terminal = e.get("terminal_return")
        hit = e.get("hit_10x")
        if not ticker or not version or horizon <= 0:
            raise ValueError(f"event[{i}] missing identifier/version/horizon")
        if source > signal or signal > source_asof:
            raise ValueError(f"event[{i}] lookahead/source unavailable at signal")
        if not isinstance(completed, bool):
            raise ValueError(f"event[{i}] missing completed boolean")
        if completed:
            if terminal is None or not math.isfinite(float(terminal)) or not isinstance(hit,bool):
                raise ValueError(f"event[{i}] incomplete mature outcome")
        elif terminal is not None or hit is not None:
            raise ValueError(f"event[{i}] censored record has future outcome")
        rows.append((i,ticker,signal.isoformat(),source.isoformat(),version,horizon,
                     int(completed),float(terminal) if completed else None,
                     int(hit) if completed else None,"SOURCE_PIT_NOT_INDEPENDENTLY_VERIFIED"))
    digest = _sha(path)
    conn = connect(db_path)
    try:
        existing = conn.execute("SELECT id FROM learning_v2_sources WHERE sha256=?",(digest,)).fetchone()
        if not existing:
            with conn:
                conn.execute("""INSERT INTO learning_v2_sources
                 (sha256,kind,imported_at,as_of,n_total,n_complete,claimed_pit)
                 VALUES (?,?,?,?,?,?,?)""",
                 (digest,"DAILY_EVENT_BACKTEST",datetime.now(timezone.utc).isoformat(),
                  source_asof.isoformat(),len(rows),sum(r[6] for r in rows),
                  int(meta.get("pit_verified") is True)))
                source_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                conn.executemany("""INSERT INTO learning_v2_outcomes
                  (source_id,source_ordinal,ticker,signal_date,source_as_of,model_version,
                   horizon_sessions,completed,terminal_return,hit_10x,provenance)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?)""",[(source_id,*r) for r in rows])
        return {"engine":ENGINE,"status":"DUPLICATE" if existing else "IMPORTED",
                "source_sha256":digest,"n_total":len(rows),"n_completed":sum(r[6] for r in rows),
                "n_censored":len(rows)-sum(r[6] for r in rows),
                "pit_independently_verified":False,
                "learning_type":"EVIDENCE_JOURNAL_NOT_MODEL_TRAINING",
                "db_path":str(Path(db_path).resolve())}
    finally:
        conn.close()


def record_feedback(db_path,category,note,source_ref):
    if not note.strip() or not source_ref.strip():
        raise ValueError("feedback requires note and evidence reference")
    conn=connect(db_path)
    try:
        with conn:
            conn.execute("""INSERT INTO learning_v2_feedback
               (category,note,source_ref,created_at) VALUES (?,?,?,?)""",
               (category.upper(),note,source_ref,datetime.now(timezone.utc).isoformat()))
    finally:
        conn.close()
    return {"engine":ENGINE,"status":"FEEDBACK_RECORDED"}


def audit(db_path,phase13_manifest=None):
    conn=connect(db_path)
    try:
        n=conn.execute("SELECT COUNT(*) FROM learning_v2_sources").fetchone()[0]
        all_events,complete=conn.execute("""SELECT COUNT(*),
          COALESCE(SUM(completed),0) FROM learning_v2_outcomes""").fetchone()
        feedback=conn.execute("SELECT COUNT(*) FROM learning_v2_feedback").fetchone()[0]
        pit_claims=conn.execute("SELECT COALESCE(SUM(claimed_pit),0) FROM learning_v2_sources").fetchone()[0]
    finally:
        conn.close()
    issues=[]
    if not n:issues.append({"priority":"P0","issue":"NO_HISTORICAL_BACKTEST_EVIDENCE","fix":"Run WF9 and import real backtest JSON"})
    if not pit_claims:issues.append({"priority":"P0","issue":"PIT_NOT_AUDITED","fix":"Obtain dated universe, delistings, available_at timestamps and independent audit"})
    if complete<100:issues.append({"priority":"P1","issue":"INSUFFICIENT_MATURE_OUTCOMES","fix":"Collect hundreds of independent completed outcomes and matched controls"})
    if phase13_manifest:
        p=Path(phase13_manifest)
        if not p.is_file():issues.append({"priority":"P0","issue":"PHASE13_MANIFEST_MISSING","fix":"Run phase13_export_signals on a COMPLETE WF5 run"})
        else:
            man=json.loads(p.read_text(encoding="utf-8"))
            if man.get("pit_verified") is not True:
                issues.append({"priority":"P0","issue":"PHASE13_EXPORT_NOT_PIT_VERIFIED","fix":"Independently audit historical membership and features"})
    issues.append({"priority":"P1","issue":"REMOTE_BACKUP_NOT_VERIFIED","fix":"Configure rclone Google Drive remote and run verified copy; never sync a live SQLite file"})
    return {"engine":ENGINE,"status":"DIAGNOSTICS_ONLY","sources":n,"events":all_events,
            "completed":complete,"feedback":feedback,"pit_source_claims":pit_claims,
            "issues":issues,"canonical_models_modified":False}


def backup(db_path, out_dir):
    """SQLite online-backup API for consistency; byte-level hash manifest."""
    source=Path(db_path)
    if not source.is_file():
        raise ValueError("No local learning database to backup")
    target=Path(out_dir)
    target.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest=target/f"meridyen-learning-v2-{stamp}.sqlite3"
    src=sqlite3.connect(f"file:{source.resolve()}?mode=ro",uri=True)
    dst=sqlite3.connect(dest)
    try:
        src.backup(dst)
        check=dst.execute("PRAGMA integrity_check").fetchone()[0]
        if check!="ok":raise ValueError("SQLite backup integrity_check failed")
    finally:
        dst.close()
        src.close()
    manifest={"engine":ENGINE,"version":SCHEMA_VERSION,"database_file":dest.name,
              "sha256":_sha(dest),"integrity":"ok","created_at":datetime.now(timezone.utc).isoformat(),
              "storage_status":"LOCAL_BACKUP_ONLY_NOT_UPLOADED",
              "confidentiality":"DO_NOT_COMMIT_TO_PUBLIC_GITHUB",
              "drive_target_folder_id":"1Bgz9m2m9qiTKgToBg-LZG9VUsGIDzYrz"}
    manifest_file=dest.with_suffix(".manifest.json")
    manifest_file.write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    return {"file":str(dest),"manifest_file":str(manifest_file),**manifest}
