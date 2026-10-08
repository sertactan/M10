from __future__ import annotations

"""Import Meridyen SEC pilot research evidence into the private Learning V2 DB.

This is **research provenance**, not training/backtest outcome ingestion.
Both extracted-folder and ZIP inputs work. The original files and hashes
are preserved, canonical S15/S16 models are never touched.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import sqlite3
from datetime import date, datetime, timezone
from zipfile import ZipFile, BadZipFile

from core.learning_v2.journal import connect

SCHEMA = "MERIDYEN_REAL_SEC_PILOT_V1"
MODES = frozenset(("inflection", "earnings", "stock", "dcf", "comps",
                   "audit", "catalysts", "pitch"))
STATUSES = frozenset(("CALCULATED_NONCANONICAL", "BLOCKED_INSUFFICIENT_DATA",
                       "TIEOUT_PASS", "ISSUES_FOUND", "WINDOW_ESTIMATES_ONLY",
                       "SCREEN_GRADE_ONLY"))
MAX_FILE_BYTES = 2_000_000
MAX_RUNS = 3000


def _json(raw: bytes, name: str):
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError(f"{name}: file too large")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{name}: invalid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{name}: expected JSON object")
    return value


def _safe_name(path: str):
    p = PurePosixPath(path)
    if (p.is_absolute() or ".." in p.parts or "\\" in path or
            len(p.parts) != 2 or p.parts[0] != "results" or
            not p.name.endswith(".json")):
        raise ValueError("Unsafe or unsupported result path: " + path)
    return str(p)


def _read_source(source: Path):
    if not source.is_file() and not source.is_dir():
        raise ValueError("Research pilot ZIP or directory not found")
    if source.is_dir():
        root = source.resolve()
        def reader(path: str):
            rel = "run_manifest.json" if path == "run_manifest.json" else _safe_name(path)
            p = (root / rel).resolve()
            if not p.is_relative_to(root) or not p.is_file():
                raise ValueError("Missing or unsafe research file: " + rel)
            if p.stat().st_size > MAX_FILE_BYTES:
                raise ValueError("Research file exceeds size bound")
            return p.read_bytes()
        return reader, None
    try:
        archive = ZipFile(source, "r")
        entries = set(archive.namelist())
        if "run_manifest.json" not in entries:
            archive.close()
            raise ValueError("Research ZIP missing root run_manifest.json")
        def reader(path: str):
            rel = "run_manifest.json" if path == "run_manifest.json" else _safe_name(path)
            if rel not in entries:
                raise ValueError("Missing research ZIP entry: " + rel)
            info = archive.getinfo(rel)
            if info.file_size > MAX_FILE_BYTES or info.is_dir():
                raise ValueError("Invalid research ZIP member size or type")
            data = archive.read(info)
            if len(data) > MAX_FILE_BYTES:
                raise ValueError("Research ZIP entry exceeds size bound")
            return data
        return reader, archive
    except (BadZipFile, OSError) as exc:
        raise ValueError("Invalid research ZIP") from exc


def inspect_pilot(source: Path):
    reader, archive = _read_source(Path(source))
    try:
        manifest_bytes = reader("run_manifest.json")
        manifest = _json(manifest_bytes, "run_manifest.json")
        meta = manifest.get("metadata")
        runs = manifest.get("runs")
        if not isinstance(meta, dict) or meta.get("schema") != SCHEMA:
            raise ValueError("Research pilot manifest schema mismatch")
        if meta.get("pit_certified") is not False:
            raise ValueError("Only explicitly non-PIT research reports can enter research journal")
        if meta.get("is_historical_backtest") is not False:
            raise ValueError("Research import cannot contain backtest labels")
        if meta.get("mature_outcomes") != 0 or meta.get("canonical_signal_count") != 0:
            raise ValueError("Research pilot cannot claim mature or canonical outcomes")
        asof = str(meta.get("as_of"))
        try:
            date.fromisoformat(asof)
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid manifest as_of") from exc
        urls = meta.get("source_urls")
        if not isinstance(urls, dict) or not urls:
            raise ValueError("Primary source URL mapping required")
        if not isinstance(runs, list) or not (1 <= len(runs) <= MAX_RUNS):
            raise ValueError("Research run list missing or too large")
        rows, seen = [], set()
        for i, run in enumerate(runs):
            if not isinstance(run, dict):
                raise ValueError(f"Run {i}: not an object")
            ticker = str(run.get("ticker") or "").strip().upper()
            mode = str(run.get("mode") or "")
            status = str(run.get("status") or "")
            path = _safe_name(str(run.get("result_path") or ""))
            digest = str(run.get("result_sha256") or "")
            if not ticker or ticker not in urls:
                raise ValueError(f"Run {i}: ticker missing from source mapping")
            if mode not in MODES or status not in STATUSES:
                raise ValueError(f"Run {i}: unknown mode or status")
            if (ticker, mode) in seen:
                raise ValueError(f"Run {i}: duplicate ticker/mode")
            seen.add((ticker, mode))
            raw = reader(path)
            actual = hashlib.sha256(raw).hexdigest()
            if actual != digest:
                raise ValueError(f"Run {i}: SHA256 mismatch")
            obj = _json(raw, path)
            if str(obj.get("ticker") or "").upper() != ticker or obj.get("mode") != mode or obj.get("as_of") != asof:
                raise ValueError(f"Run {i}: payload/manifest identifier mismatch")
            if obj.get("pit_certified") is True:
                raise ValueError(f"Run {i}: research result falsely claims PIT certified")
            if status == "BLOCKED_INSUFFICIENT_DATA" and not obj.get("error"):
                raise ValueError(f"Run {i}: blocked run missing error reason")
            if status != "BLOCKED_INSUFFICIENT_DATA" and obj.get("error"):
                raise ValueError(f"Run {i}: success run contains error")
            rows.append((ticker, mode, status, path, digest, raw.decode("utf-8")))
        return {
            "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "manifest_json": manifest_bytes.decode("utf-8"),
            "as_of": asof,
            "runs": rows,
            "ticker_count": len(set(r[0] for r in rows)),
        }
    finally:
        if archive:
            archive.close()


def import_pilot(db_path: Path, source: Path):
    """Atomic, idempotent ingest to separate research tables only."""
    data = inspect_pilot(source)  # Validate ALL records before modifying a database.
    conn = connect(db_path)
    try:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS learning_v2_research_sources (
            manifest_sha256 TEXT PRIMARY KEY,
            research_schema TEXT NOT NULL,
            as_of TEXT NOT NULL,
            imported_at TEXT NOT NULL,
            n_runs INTEGER NOT NULL,
            status TEXT NOT NULL,
            manifest_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS learning_v2_research_observations (
            manifest_sha256 TEXT NOT NULL REFERENCES learning_v2_research_sources(manifest_sha256),
            ticker TEXT NOT NULL,
            mode TEXT NOT NULL,
            status TEXT NOT NULL,
            result_path TEXT NOT NULL,
            result_sha256 TEXT NOT NULL,
            output_json TEXT NOT NULL,
            PRIMARY KEY (manifest_sha256,ticker,mode)
        );
        """)
        existing = conn.execute(
            "SELECT manifest_sha256 FROM learning_v2_research_sources WHERE manifest_sha256=?",
            (data["manifest_sha256"],),
        ).fetchone()
        if existing:
            n = conn.execute(
                "SELECT COUNT(*) FROM learning_v2_research_observations WHERE manifest_sha256=?",
                (data["manifest_sha256"],),
            ).fetchone()[0]
            if n != len(data["runs"]):
                raise ValueError("Existing research manifest has incomplete rows; repair required")
        else:
            with conn:
                conn.execute("""INSERT INTO learning_v2_research_sources
                  (manifest_sha256,research_schema,as_of,imported_at,n_runs,status,manifest_json)
                  VALUES (?,?,?,?,?,?,?)""",
                  (data["manifest_sha256"], SCHEMA, data["as_of"],
                   datetime.now(timezone.utc).isoformat(), len(data["runs"]),
                   "NONCANONICAL_RESEARCH_ONLY", data["manifest_json"]))
                conn.executemany("""INSERT INTO learning_v2_research_observations
                   (manifest_sha256,ticker,mode,status,result_path,result_sha256,output_json)
                   VALUES (?,?,?,?,?,?,?)""",
                   ((data["manifest_sha256"], *r) for r in data["runs"]))
        return {
            "status": "DUPLICATE" if existing else "RESEARCH_IMPORTED",
            "research_source_sha256": data["manifest_sha256"],
            "tickers": data["ticker_count"],
            "research_routes": len(data["runs"]),
            "mature_outcomes_imported": 0,
            "canonical_scores_updated": 0,
            "learning_mode": "EVIDENCE_JOURNAL_NOT_MODEL_TRAINING",
            "database": str(Path(db_path)),
        }
    finally:
        conn.close()


def audit_research(db_path: Path):
    conn = connect(db_path)
    try:
        t = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='learning_v2_research_sources'"
        ).fetchone()
        if not t:
            return {"status":"NO_RESEARCH_JOURNAL", "research_sources":0,"research_routes":0}
        n = conn.execute("SELECT COUNT(*) FROM learning_v2_research_sources").fetchone()[0]
        rows = conn.execute(
            "SELECT status,COUNT(*) FROM learning_v2_research_observations GROUP BY status"
        ).fetchall()
        return {
            "status": "RESEARCH_EVIDENCE_AVAILABLE" if n else "NO_RESEARCH_JOURNAL",
            "research_sources": n, "research_routes": sum(r[1] for r in rows),
            "route_statuses": {r[0]: r[1] for r in rows},
            "canonical_learning": "NOT_TRAINED_OR_PROMOTED",
        }
    finally:
        conn.close()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db",type=Path,default=Path("data/runtime/meridyen_learning.sqlite3"))
    sub=ap.add_subparsers(dest="action",required=True)
    ingest=sub.add_parser("import")
    ingest.add_argument("--bundle",type=Path,required=True,
                        help="Extracted pilot directory or ZIP containing root run_manifest.json")
    sub.add_parser("audit")
    args=ap.parse_args()
    try:
        result = import_pilot(args.db,args.bundle) if args.action=="import" else audit_research(args.db)
        print(json.dumps(result,indent=2,ensure_ascii=False))
    except (ValueError,OSError,sqlite3.Error,BadZipFile,json.JSONDecodeError) as exc:
        ap.exit(2,"RESEARCH_IMPORT_BLOCKED: "+str(exc)+"\n")


if __name__=="__main__":
    main()
