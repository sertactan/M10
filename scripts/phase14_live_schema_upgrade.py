from __future__ import annotations

"""Phase14 guarded Windows schema migration from a *verified* on-copy preview.

Defaults to READ-ONLY preparation. Live replacement needs all of:
  --apply --confirm-app-closed --confirm-source-exact <absolute source path>

Never pulls historical stock data, modifies canonical S15/S16 definitions,
automatically closes M10, or overwrites a user's existing backup.
"""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
from uuid import uuid4

from scripts.phase14_schema_preview import (
    _digest, _integrity, _read_only, _tables_and_counts, preview, REQUIRED,
)

SCHEMA = "MERIDYEN_PHASE14_GUARDED_SCHEMA_APPLY_V1"


def _sidecar_paths(db: Path):
    return [Path(str(db) + suffix) for suffix in ("-wal", "-shm", "-journal")]


def _refuse_active_journals(db: Path):
    present = [x.name for x in _sidecar_paths(db) if x.exists()]
    if present:
        raise ValueError(
            "SQLite journal/sidecar detected; close M10 completely and check "
            "the database before migration: " + ", ".join(present)
        )


def _verify_counts(path: Path, original_counts: dict[str, int]) -> None:
    with closing(_read_only(path)) as conn:
        if _integrity(conn) != "ok":
            raise ValueError("Migrated database failed integrity_check")
        observed = _tables_and_counts(conn)
    if any(observed.get(t) != n for t, n in original_counts.items()):
        raise ValueError("One or more original table counts changed")
    if not set(REQUIRED).issubset(observed):
        raise ValueError("Migrated database has missing required WF5/WF6 tables")


def migrate(
    source_db: Path,
    backup_dir: Path,
    *,
    apply: bool = False,
    confirm_app_closed: bool = False,
    confirm_source_exact: str | None = None,
    repo_root: Path | None = None,
):
    """Safe plan, or explicit offline install with unique retained rollback.

    A SQLite online backup is made by the copy-only preview.  The tested
    migrated DB is copied to a sibling staging file in the SAME directory as
    the live database, so OS renames never cross volumes.

    Refuses any WAL/SHM/journal sidecar (including stale files) rather than
    risking detached uncheckpointed transactions.
    """
    source = Path(source_db).expanduser().resolve()
    if not source.is_file():
        raise ValueError("Source operational.db does not exist")
    if source.is_symlink():
        raise ValueError("Source operational.db cannot be a symlink")
    backup_dir = Path(backup_dir).expanduser().resolve()
    if source.parent == backup_dir or source.is_relative_to(backup_dir):
        raise ValueError("Backup folder must be separate from the live database")
    if apply and (
        not confirm_app_closed
        or not confirm_source_exact
        or Path(confirm_source_exact).expanduser().resolve() != source
    ):
        raise ValueError(
            "Live migration requires --confirm-app-closed and "
            "--confirm-source-exact matching the live source path"
        )
    # Refuse to proceed if this SQLite DB is in WAL or rollback-journal state.
    # Never delete, checkpoint or move sidecars without the owner's approval.
    _refuse_active_journals(source)
    source_hash_before = _digest(source)
    source_stat_before = source.stat()
    result = preview(source, backup_dir, repo_root=repo_root)
    if result["status"] != "SCHEMA_PREVIEW_SAFE_ON_COPY_ONLY":
        raise ValueError("Fresh schema-on-copy preview failed: " + str(result["reason"]))
    if not result["pre_existing_rows_preserved"]:
        raise ValueError("Fresh schema preview did not preserve existing rows")
    # The copy-only preview contains a consistent snapshot and validates all
    # original row counts. No live changes have happened at this point.
    plan = {
        "schema": SCHEMA,
        "status": "APPLY_READY_REQUIRES_EXPLICIT_OWNER_CONFIRMATION",
        "source_db": str(source),
        "backup_snapshot": result["snapshot_file"],
        "preview_database": result["preview_file"],
        "snapshot_sha256": result["snapshot_sha256"],
        "preview_report": result["report_file"],
        "existing_table_counts_preserved": True,
        "missing_required_tables": [],
        "live_database_modified": False,
        "rollback_file": None,
        "historical_pit_data_added": False,
        "wf9_activated": False,
    }
    if not apply:
        return plan

    # Never trust a preview if the installed app changed any source bytes,
    # timestamps or WAL state while the online backup was running.
    if (
        _digest(source) != source_hash_before
        or source.stat().st_size != source_stat_before.st_size
        or source.stat().st_mtime_ns != source_stat_before.st_mtime_ns
    ):
        raise ValueError("Live source changed during schema preview: retry with app closed")
    _refuse_active_journals(source)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    uid = stamp + "-" + uuid4().hex[:12]
    stage = source.with_name("." + source.name + ".phase14-stage-" + uid + ".sqlite3")
    rollback = source.with_name(source.name + ".pre_phase14-" + uid + ".bak")
    if stage.exists() or rollback.exists():
        raise ValueError("Migration staging/rollback target already exists")

    with closing(_read_only(Path(result["preview_file"]))) as original:
        with closing(sqlite3.connect(stage)) as prepared:
            original.backup(prepared)
    with closing(_read_only(Path(result["snapshot_file"]))) as saved:
        original_counts = _tables_and_counts(saved)
    _verify_counts(stage, original_counts)

    # At this point source remains unchanged, staging is fully validated,
    # and there is a consistent backup on an independent volume/path.
    # We must keep the old live file alongside the installed app for a
    # manual rollback if a newer app fails after installation.
    source_moved = False
    promoted = False
    try:
        _refuse_active_journals(source)
        if (
            _digest(source) != source_hash_before
            or source.stat().st_mtime_ns != source_stat_before.st_mtime_ns
        ):
            raise ValueError("Live source changed before install; migration cancelled")
        # On Windows, a running process with a SQLite handle normally blocks
        # this rename. On all OSs owner must close M10 before applying.
        os.rename(source, rollback)
        source_moved = True
        try:
            os.rename(stage, source)
            promoted = True
        except BaseException:
            # Restore original DB if installing the staged copy fails.
            if not source.exists():
                os.rename(rollback, source)
                source_moved = False
            raise
        try:
            _verify_counts(source, original_counts)
        except BaseException:
            # Roll back immediately if post-install verification fails.
            failed = source.with_name(source.name + ".failed_phase14-" + uid)
            os.rename(source, failed)
            promoted = False
            os.rename(rollback, source)
            source_moved = False
            raise
        plan.update({
            "status": "LIVE_SCHEMA_UPGRADED_WITH_ROLLBACK_RETAINED",
            "live_database_modified": True,
            "rollback_file": str(rollback),
            "post_migration_integrity": "ok",
            "snapshot_database_kept": True,
        })
        return plan
    finally:
        # Never erase the preserved live rollback file or independent backup.
        if not promoted and stage.exists():
            stage.unlink()
        if source_moved and not source.exists():
            # Previous restore failed unexpectedly; surface an unmistakable
            # error and retain the old file, NEVER silently recreate new DB.
            raise RuntimeError(
                "Live DB path is missing after interrupted installation! "
                "Restore manually from " + str(rollback)
            )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-db", type=Path, required=True)
    p.add_argument("--backup-dir", type=Path, required=True)
    p.add_argument("--apply", action="store_true",
                   help="Opt in to updating the installed DB; default is copy-only")
    p.add_argument("--confirm-app-closed", action="store_true",
                   help="Confirm all M10 desktop/CLI processes are shut down")
    p.add_argument("--confirm-source-exact",
                   help="Repeat the full absolute source path to authorize this DB")
    args = p.parse_args()
    try:
        outcome = migrate(
            args.source_db, args.backup_dir, apply=args.apply,
            confirm_app_closed=args.confirm_app_closed,
            confirm_source_exact=args.confirm_source_exact,
        )
    except (sqlite3.Error, ValueError, OSError, RuntimeError) as exc:
        p.exit(2, "PHASE14_LIVE_SCHEMA_BLOCKED: " + str(exc) + "\n")
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
