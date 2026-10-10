from __future__ import annotations

"""Private, create-only SQLite and source snapshot with independent restore probe."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def quick_check(path: Path) -> str:
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        return str(db.execute("PRAGMA quick_check").fetchone()[0])


def backup_sqlite(source: Path, target: Path) -> None:
    if source.is_symlink() or not source.is_file() or target.exists():
        raise ValueError("SQLite source unavailable or destination exists")
    with closing(sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)) as original:
        original.execute("PRAGMA query_only=ON")
        with closing(sqlite3.connect(target)) as copy:
            original.backup(copy)
    if quick_check(target) != "ok":
        raise ValueError("SQLite backup quick_check failed")


def inventory(db: Path, source_files: dict[str, Path], out: Path) -> dict:
    if out.exists() or out.is_symlink():
        raise ValueError("Backup destination must be new")
    if not db.is_file() or db.is_symlink():
        raise ValueError("Operational SQLite unavailable")
    original_paths = [db, *source_files.values()]
    if any(not p.is_file() or p.is_symlink() for p in original_paths):
        raise ValueError("Source file missing or linked")
    resolved = [p.resolve() for p in original_paths]
    if len(set(resolved)) != len(resolved) or any(p.is_relative_to(out.resolve())
                                                  for p in resolved):
        raise ValueError("Backup would overlap a source or duplicate it")
    out.mkdir(parents=True, exist_ok=False)
    snapshots = out / "snapshots"
    restored = out / "restore_probe"
    snapshots.mkdir()
    restored.mkdir()
    entries: list[dict] = []
    try:
        for label, source in [("operational.db", db), *sorted(source_files.items())]:
            target = snapshots / label
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.suffix.lower() in {".db", ".sqlite", ".sqlite3"}:
                backup_sqlite(source, target)
                method = "SQLITE_ONLINE_BACKUP"
            else:
                before = digest(source)
                with source.open("rb") as read, target.open("xb") as write:
                    shutil.copyfileobj(read, write, 1024 * 1024)
                if digest(source) != before or digest(target) != before:
                    raise ValueError(f"Source changed during copy: {label}")
                method = "VERIFIED_FILE_COPY"
            checksum = digest(target)
            probe = restored / label
            probe.parent.mkdir(parents=True, exist_ok=True)
            with target.open("rb") as read, probe.open("xb") as write:
                shutil.copyfileobj(read, write, 1024 * 1024)
            if digest(probe) != checksum:
                raise ValueError(f"Restore probe hash mismatch: {label}")
            sqlite_status = quick_check(probe) if method == "SQLITE_ONLINE_BACKUP" else None
            if sqlite_status not in (None, "ok"):
                raise ValueError(f"Restore probe SQLite check failed: {label}")
            entries.append({"label": label, "source": str(source), "bytes": target.stat().st_size,
                            "sha256": checksum, "method": method,
                            "backup_quick_check": "ok" if method == "SQLITE_ONLINE_BACKUP" else None,
                            "restored_quick_check": sqlite_status,
                            "restored_sha256_matches": True})
        result = {"schema": "MERIDYEN_PHASE26A_PRIVATE_BACKUP_V1",
                  "status": "BACKUP_AND_RESTORE_VERIFIED",
                  "created_utc": datetime.now(timezone.utc).isoformat(),
                  "source_db_opened_read_only": True,
                  "source_files_modified": False,
                  "canonical_accepted_securities": 0,
                  "entries": entries}
    except Exception:
        result = {"schema": "MERIDYEN_PHASE26A_PRIVATE_BACKUP_V1",
                  "status": "INCOMPLETE_DO_NOT_RESTORE", "entries": entries}
        (out / "manifest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        raise
    (out / "manifest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def collect_private_sources(runtime: Path, original_price: Path) -> dict[str, Path]:
    files = {"original_price/us-shareprices-daily.csv": original_price}
    for phase in ("phase19/pit_staging", "phase25q/staged_datasets", "phase25r",
                  "phase25s", "phase25w", "phase25x", "phase25y", "phase25z"):
        directory = runtime / phase
        if not directory.is_dir() or directory.is_symlink():
            raise ValueError(f"Required private source directory missing: {phase}")
        for path in directory.rglob("*"):
            if path.is_file():
                files[f"runtime/{path.relative_to(runtime).as_posix()}"] = path
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--price-csv", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    runtime = args.runtime.resolve()
    files = collect_private_sources(runtime, args.price_csv)
    result = inventory(runtime / "data" / "runtime" / "operational.db", files, args.out)
    print(json.dumps({"status": result["status"], "entries": len(result["entries"]),
                      "bytes": sum(row["bytes"] for row in result["entries"]),
                      "manifest": str(args.out / "manifest.json")}))


if __name__ == "__main__":
    main()
