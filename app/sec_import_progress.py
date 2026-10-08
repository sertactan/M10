from __future__ import annotations

"""Future SEC bulk imports: local progress checkpoints and exclusive process lock.

THIS DOES NOT TRACK imports already started before this code is deployed.
No database writes or API calls occur here. Lock files are exclusive but not
an OS-wide guarantee against legacy importers that do not use this lock.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from uuid import uuid4


SCHEMA = "MERIDYEN_SEC_BULK_PROGRESS_V1"
PROGRESS_FILE = "companyfacts-progress.json"
LOCK_FILE = "companyfacts-import.lock"


class SECImportBusy(RuntimeError):
    """Concurrent modern SEC ZIP importer denied, never silently fallback."""


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_json(path: Path, payload: dict) -> None:
    # Not stored in GitHub or private portfolio/SEC source data; no API keys.
    if path.is_symlink():
        raise ValueError("SEC progress status path is symlink")
    temp = path.parent / ("." + path.name + "." + uuid4().hex + ".tmp")
    try:
        with temp.open("x", encoding="utf-8") as f:
            json.dump(payload, f, sort_keys=True, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


class SECImportProgress:
    def __init__(self, archive_dir: Path, *, checkpoint_every: int = 25) -> None:
        self.folder = Path(archive_dir)
        self.lock = self.folder / LOCK_FILE
        self.status = self.folder / PROGRESS_FILE
        self.checkpoint_every = max(1, int(checkpoint_every))
        self.record: dict = {}
        self._owned = False

    def __enter__(self) -> "SECImportProgress":
        self.folder.mkdir(parents=True, exist_ok=True)
        # Fail closed if an old crash left an unresolved lock: don't delete
        # a possibly active process's marker automatically.
        try:
            fd = os.open(self.lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as exc:
            raise SECImportBusy(
                "SEC bulk import lock exists; inspect its owner. "
                "Do not start a duplicate importer or auto-delete the lock."
            ) from exc
        self._owned = True
        self.record = {
            "schema": SCHEMA,
            "run_id": uuid4().hex,
            "pid": os.getpid(),
            "started_utc": _utc(),
            "updated_utc": _utc(),
            "stage": "STARTING",
            "entries_total": None,
            "entries_scanned": 0,
            "matched_issuers_saved": 0,
            "facts_written_this_run": 0,
            "error_class": None,
            "complete_archive_processed": False,
            "independently_verified": False,
        }
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump({"schema": SCHEMA, "run_id": self.record["run_id"],
                           "pid": os.getpid(), "started_utc": self.record["started_utc"]}, handle)
                handle.write("\n")
            _atomic_json(self.status, self.record)
        except BaseException:
            self.lock.unlink(missing_ok=True)
            self._owned = False
            raise
        return self

    def checkpoint(self, *, entries_total: int | None = None,
                   entries_scanned: int | None = None,
                   securities: int | None = None,
                   facts: int | None = None, stage: str = "IMPORTING") -> None:
        if not self._owned:
            raise RuntimeError("Not holding SEC ZIP import lock")
        values = {}
        if entries_total is not None:
            values["entries_total"] = int(entries_total)
        if entries_scanned is not None:
            values["entries_scanned"] = int(entries_scanned)
        if securities is not None:
            values["matched_issuers_saved"] = int(securities)
        if facts is not None:
            values["facts_written_this_run"] = int(facts)
        self.record.update(values)
        self.record["updated_utc"] = _utc()
        self.record["stage"] = stage
        _atomic_json(self.status, self.record)

    def __exit__(self, exc_type, exc, tb) -> None:
        if not self._owned:
            return
        try:
            self.record["stage"] = "FAILED" if exc_type is not None else "FINISHED"
            self.record["updated_utc"] = _utc()
            self.record["error_class"] = exc_type.__name__ if exc_type is not None else None
            self.record["complete_archive_processed"] = exc_type is None and (
                self.record["entries_total"] is not None
                and self.record["entries_scanned"] == self.record["entries_total"]
            )
            self.record["independently_verified"] = False
            _atomic_json(self.status, self.record)
        finally:
            # We own this lock since exclusive creation in this context.
            self.lock.unlink(missing_ok=True)
            self._owned = False
