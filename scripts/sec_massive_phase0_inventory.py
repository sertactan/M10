from __future__ import annotations

"""SEC/Massive Phase 0: local read-only metadata inventory.

No API requests, SQLite connections, source imports, DB writes, model scoring,
trading, background processes, or vendor credential reads from local .env files.
A finished SEC progress checkpoint is NOT proof of full/canonical SEC coverage.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Mapping

SCHEMA = "MERIDYEN_SEC_MASSIVE_PHASE0_INVENTORY_V1"
PROGRESS_SCHEMA = "MERIDYEN_SEC_BULK_PROGRESS_V1"
MAX_PROGRESS_BYTES = 200_000
STAGES = {"STARTING", "IMPORTING", "FINALIZING", "FINISHED", "FAILED"}


def _artifact(path: Path) -> str:
    if path.is_symlink():
        return "UNSAFE_SYMLINK"
    if path.is_file():
        return "FILE_PRESENT_UNVERIFIED"
    if path.exists():
        return "UNEXPECTED_PATH_TYPE"
    return "NOT_FOUND"


def _checkpoint(path: Path) -> dict:
    found = _artifact(path)
    if found != "FILE_PRESENT_UNVERIFIED":
        return {"state": found, "import_completed": False}
    try:
        if path.stat().st_size > MAX_PROGRESS_BYTES:
            return {"state": "INVALID_OVERSIZE", "import_completed": False}
        record = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(record, dict) or record.get("schema") != PROGRESS_SCHEMA:
            return {"state": "INVALID_SCHEMA", "import_completed": False}
        stage = record.get("stage")
        total = record.get("entries_total")
        scanned = record.get("entries_scanned")
        complete = record.get("complete_archive_processed")
        if (stage not in STAGES or type(scanned) is not int or scanned < 0
                or (total is not None and (type(total) is not int or total < 0))
                or (total is not None and scanned > total)
                or type(complete) is not bool):
            return {"state": "INVALID_FIELDS", "import_completed": False}
        asserted_finish = (stage == "FINISHED" and complete is True
                           and type(total) is int and total > 0 and scanned == total)
        return {
            "state": "INSTRUMENTED_IMPORT_FINISHED_UNVERIFIED"
                     if asserted_finish else "INSTRUMENTED_PROGRESS_PRESENT",
            "stage": stage,
            "entries_scanned": scanned,
            "entries_total": total,
            "run_finish_asserted": asserted_finish,
            "import_completed": False,
        }
    except (ValueError, UnicodeError, OSError):
        return {"state": "UNREADABLE_OR_INVALID_JSON", "import_completed": False}


def build_report(runtime_root: Path, environ: Mapping[str, str] | None = None) -> dict:
    """Read only path metadata, bounded SEC checkpoint and process ENV flags.

    Does NOT check whether a legacy SEC importer is still running. Never
    interprets credentials, ZIP existence or a progress file as PIT readiness.
    """
    root = Path(runtime_root).expanduser()
    env = os.environ if environ is None else environ
    root_status = ("UNSAFE_SYMLINK" if root.is_symlink()
                   else "DIRECTORY_PRESENT" if root.is_dir()
                   else "MISSING_OR_NOT_DIRECTORY")
    if root_status != "DIRECTORY_PRESENT":
        return {
            "schema": SCHEMA,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "BLOCKED_RUNTIME_NOT_CONFIRMED",
            "runtime_root_status": root_status,
            "sec_import_running": "UNKNOWN",
            "wf9_activated": False,
            "pit_independently_certified": False,
            "next_actions": ["Locate the actual writable Windows M10 runtime; do not start an importer."],
        }
    archive = root / "bulk" / "sec"
    progress = _checkpoint(archive / "companyfacts-progress.json")
    lock = _artifact(archive / "companyfacts-import.lock")
    archive_zip = _artifact(archive / "companyfacts.zip")
    partial_zip = _artifact(archive / "companyfacts.zip.part")
    credentials = {
        "massive_process_environment_configured": bool((env.get("MASSIVE_API_KEY") or "").strip()),
        "alphavantage_process_environment_configured": bool((env.get("ALPHAVANTAGE_API_KEY") or "").strip()),
        "sec_user_agent_process_environment_configured": bool((env.get("SEC_USER_AGENT") or "").strip()),
        "local_dotenv_examined": False,
        "massive_historical_entitlement_verified": False,
    }
    return {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "EVIDENCE_ONLY_NOT_CERTIFIED",
        "runtime_root_status": root_status,
        "sec": {
            "companyfacts_zip": archive_zip,
            "companyfacts_partial_zip": partial_zip,
            "instrumented_progress": progress,
            "instrumented_import_lock": lock,
            "legacy_import_running": "UNKNOWN_REQUIRES_TASK_MANAGER_CHECK",
            "full_fundamentals_loaded": "NOT_VERIFIED",
            "original_accepted_at_audited": False,
        },
        "massive": {
            **credentials,
            "historical_price_data_loaded": "NOT_VERIFIED",
            "splits_dividends_delisting_verified": False,
        },
        "storage": {
            "operational_db": _artifact(root / "data" / "runtime" / "operational.db"),
            "parquet_root": ("UNSAFE_SYMLINK" if (root / "data" / "runtime" / "parquet").is_symlink()
                             else "DIRECTORY_PRESENT" if (root / "data" / "runtime" / "parquet").is_dir()
                             else "NOT_FOUND"),
            "sqlite_opened": False,
            "parquet_contents_scanned": False,
        },
        "pit_snapshots": {"required": 144, "actual": None, "status": "NOT_MEASURED"},
        "sec_import_running": "UNKNOWN",
        "safe_to_start_second_import": False,
        "paid_api_called": False,
        "database_modified": False,
        "wf9_activated": False,
        "pit_independently_certified": False,
        "next_actions": [
            "Verify existing/legacy SEC import process in Windows Task Manager; do not restart or delete locks.",
            "After import completion, make a SQLite online backup and run existing Phase13/14/18 read-only audits.",
            "Check Massive key presence AND historical entitlement in the owner's private environment; do not reveal credentials.",
            "Obtain exact source/date coverage and corporate-action/delisting evidence before any WF9 activation.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", type=Path, required=True,
                        help="Actual M10 writable Windows runtime; no path guessing.")
    args = parser.parse_args(argv)
    report = build_report(args.runtime_root)
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0  # Evidence report is not a production-ready declaration.


if __name__ == "__main__":
    raise SystemExit(main())
