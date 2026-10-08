from __future__ import annotations

"""Phase 14: preview current M10 schema on a verified SQLite ONLINE BACKUP.

This script NEVER modifies the source operational.db. It creates two separate
copies outside public GitHub: an immutable, consistent pre-migration snapshot
and a schema-preview copy. It tests M10's real SQLiteStore.initialize() only
against the second copy, comparing ALL pre-existing table row counts before/
after and checking SQLite integrity. Do not upload the private backups.
"""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from data.database.sqlite_store import SQLiteStore

REQUIRED = (
    "wf5_replay_runs", "wf5_replay_observations", "wf5_replay_checkpoints",
    "wf6_walk_forward_runs", "wf6_walk_forward_folds", "wf6_oos_observations",
    "wf6_holdout_locks", "forward_outcomes",
)
SCHEMA = "MERIDYEN_PHASE14_SCHEMA_PREVIEW_V1"


def _read_only(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def _integrity(conn: sqlite3.Connection) -> str:
    rows = [str(r[0]) for r in conn.execute("PRAGMA integrity_check")]
    return "ok" if rows == ["ok"] else "; ".join(rows[:3])


def _tables_and_counts(conn: sqlite3.Connection) -> dict[str, int]:
    names = [
        str(row[0]) for row in conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    out = {}
    for name in names:
        quoted = '"' + name.replace('"', '""') + '"'
        out[name] = int(conn.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()[0])
    return out


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def preview(source_db: Path, backup_dir: Path, *, repo_root: Path | None = None) -> dict:
    src = Path(source_db).expanduser().resolve()
    dest = Path(backup_dir).expanduser().resolve()
    repo = Path(repo_root or Path(__file__).resolve().parents[1]).resolve()
    if not src.is_file():
        raise ValueError("Source M10 operational.db was not found")
    if src.suffix.lower() not in (".db", ".sqlite", ".sqlite3"):
        raise ValueError("Only a local SQLite source file is supported")
    if src == dest or dest == repo or dest.is_relative_to(repo):
        raise ValueError("Backups must be outside the public M10 source repository")
    if src.is_relative_to(dest):
        raise ValueError("Source operational.db must not be inside backup directory")
    dest.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    identity = stamp + "-" + uuid4().hex[:12]
    snapshot = dest / f"operational_pre_schema_{identity}.sqlite3"
    staged = dest / f"phase14_schema_preview_{identity}.sqlite3"
    report_file = dest / f"phase14_schema_preview_{identity}.json"
    report = {
        "schema": SCHEMA,
        "status": "SCHEMA_PREVIEW_BLOCKED",
        "source_db": str(src),
        "source_open_mode": "READ_ONLY",
        "live_source_mutated": False,
        "snapshot_file": str(snapshot),
        "preview_file": str(staged),
        "report_file": str(report_file),
        "snapshot_integrity": "NOT_TESTED",
        "preview_integrity": "NOT_TESTED",
        "snapshot_sha256": None,
        "pre_existing_tables": None,
        "added_schema_tables": [],
        "missing_required_tables": list(REQUIRED),
        "pre_existing_rows_preserved": False,
        "wf9_activated": False,
        "historical_pit_loaded": False,
        "reason": None,
    }
    try:
        with closing(_read_only(src)) as original:
            if _integrity(original) != "ok":
                raise ValueError("Original database integrity check failed")
            # SQLite backup API safely includes committed WAL state.
            with closing(sqlite3.connect(snapshot)) as copy:
                original.backup(copy)
        with closing(_read_only(snapshot)) as saved:
            if _integrity(saved) != "ok":
                raise ValueError("Online backup SQLite integrity check failed")
            before = _tables_and_counts(saved)
        report["snapshot_integrity"] = "ok"
        report["snapshot_sha256"] = _digest(snapshot)
        report["pre_existing_tables"] = len(before)
        # A second SQLite online copy isolates the schema migration.
        with _read_only(snapshot) as saved:
            with closing(sqlite3.connect(staged)) as copy:
                saved.backup(copy)
        store = SQLiteStore(staged)
        try:
            # recover_corrupt=False: a migration must never silently replace
            # a damaged preview with a new empty database.
            store.initialize(recover_corrupt=False)
        finally:
            store.close()
        with closing(_read_only(staged)) as check:
            integrity = _integrity(check)
            after = _tables_and_counts(check)
        report["preview_integrity"] = integrity
        report["added_schema_tables"] = sorted(set(after) - set(before))
        report["missing_required_tables"] = sorted(set(REQUIRED) - set(after))
        changed = {
            name: {"before": count, "after": after.get(name)}
            for name, count in before.items()
            if after.get(name) != count
        }
        report["changed_pre_existing_table_counts"] = changed
        report["pre_existing_rows_preserved"] = not changed
        if integrity != "ok" or changed or report["missing_required_tables"]:
            raise ValueError("Schema preview failed integrity, row-count, or required-table check")
        # Backups are never automatically promoted into the running app.
        report["status"] = "SCHEMA_PREVIEW_SAFE_ON_COPY_ONLY"
    except (sqlite3.Error, OSError, RuntimeError, ValueError) as exc:
        report["reason"] = f"{type(exc).__name__}: {exc}"
    report_file.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    return report


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-db", type=Path, required=True)
    p.add_argument("--backup-dir", type=Path, required=True)
    args = p.parse_args()
    try:
        result = preview(args.source_db, args.backup_dir)
    except (ValueError, OSError) as exc:
        p.exit(2, "PHASE14_SCHEMA_PREVIEW_BLOCKED: " + str(exc) + "\n")
    print(json.dumps({
        "status": result["status"],
        "snapshot_integrity": result["snapshot_integrity"],
        "preview_integrity": result["preview_integrity"],
        "pre_existing_rows_preserved": result["pre_existing_rows_preserved"],
        "added_schema_tables": result["added_schema_tables"],
        "missing_required_tables": result["missing_required_tables"],
        "report": result["report_file"],
        "reason": result["reason"],
        "source_modified": False,
    }, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "SCHEMA_PREVIEW_SAFE_ON_COPY_ONLY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
