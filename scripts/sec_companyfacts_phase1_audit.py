from __future__ import annotations

"""Phase 1: offline, operator-gated SEC Companyfacts completion evidence.

No networking, source database writes, backup creation, background importer,
vendor credential reads, or SEC/PIT certification. Without explicit human
confirmation that *legacy and modern* importers are stopped, this only reads
the Phase0 metadata inventory (no ZIP or SQLite contents).
"""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sqlite3
import zipfile

from scripts.sec_massive_phase0_inventory import build_report as phase0_report

SCHEMA = "MERIDYEN_SEC_PHASE1_COMPLETION_AUDIT_V1"
MAX_MEMBERS = 100_000
CIK_FILE = re.compile(r"CIK(\d{10})\.json", flags=re.IGNORECASE)
REQUIRED_TABLES = frozenset(("fundamental_facts_source", "security_master"))


def _archive_inventory(path: Path, *, verify_crc: bool = False) -> dict:
    result = {
        "state": "NOT_CHECKED", "member_count": None, "issuer_document_count": None,
        "duplicate_cik_count": None, "crc_checked": False,
        "payload_integrity_verified": False,
    }
    if path.is_symlink() or not path.is_file():
        result["state"] = "UNSAFE_OR_MISSING_ARCHIVE"
        return result
    try:
        with zipfile.ZipFile(path, mode="r") as archive:
            entries = archive.infolist()
            if not entries or len(entries) > MAX_MEMBERS:
                result["state"] = "INVALID_MEMBER_COUNT"
                return result
            result["member_count"] = len(entries)
            ciks: set[str] = set()
            duplicate = 0
            unexpected = 0
            for info in entries:
                name = info.filename
                if (info.is_dir() or not name or "/" in name or "\\" in name
                        or name in (".", "..") or info.flag_bits & 1):
                    result["state"] = "UNSAFE_OR_ENCRYPTED_ARCHIVE_ENTRY"
                    return result
                m = CIK_FILE.fullmatch(name)
                if m is None:
                    unexpected += 1
                    continue
                if m.group(1) in ciks:
                    duplicate += 1
                ciks.add(m.group(1))
            result["issuer_document_count"] = len(ciks)
            result["duplicate_cik_count"] = duplicate
            result["unexpected_member_count"] = unexpected
            if not ciks or duplicate:
                result["state"] = "MISSING_OR_DUPLICATE_CIK_DOCUMENTS"
                return result
            if verify_crc:
                result["crc_checked"] = True
                bad = archive.testzip()
                if bad is not None:
                    result["state"] = "ZIP_MEMBER_CRC_FAILED"
                    return result
                result["payload_integrity_verified"] = True
            result["state"] = ("ZIP_CRC_VERIFIED" if verify_crc
                               else "ZIP_CENTRAL_DIRECTORY_ONLY")
    except (OSError, EOFError, ValueError, zipfile.BadZipFile, RuntimeError):
        result["state"] = "ZIP_UNREADABLE_OR_CORRUPT"
    return result



def _checkpoint_import_counts(path: Path) -> dict:
    """Read bounded, non-secret importer totals only after verified path checks."""
    result = {"facts_written_this_run": None, "matched_issuers_saved": None}
    if path.is_symlink() or not path.is_file():
        return result
    try:
        if path.stat().st_size > 200_000:
            return result
        record = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(record, dict) or record.get("schema") != "MERIDYEN_SEC_BULK_PROGRESS_V1":
            return result
        for key in result:
            value = record.get(key)
            if type(value) is int and 0 <= value <= 1_000_000_000:
                result[key] = value
    except (OSError, UnicodeError, ValueError):
        pass
    return result


def _backup_inventory(backup: Path | None, live: Path) -> dict:
    result = {
        "state": "NOT_CHECKED", "sec_fact_count": None,
        "sec_security_count": None, "sqlite_quick_check": None,
        "backup_not_live_db": False,
    }
    if backup is None:
        result["state"] = "BACKUP_NOT_PROVIDED"
        return result
    backup = Path(backup).expanduser()
    if backup.is_symlink() or not backup.is_file():
        result["state"] = "BACKUP_MISSING_OR_SYMLINK"
        return result
    try:
        if (backup.resolve() == live.resolve()
                or (live.is_file() and os.path.samefile(backup, live))):
            result["state"] = "REFUSED_LIVE_DATABASE"
            return result
    except OSError:
        result["state"] = "BACKUP_PATH_UNSAFE"
        return result
    if (Path(str(backup) + "-wal").exists()
            or Path(str(backup) + "-shm").exists()):
        result["state"] = "BACKUP_HAS_SQLITE_SIDECAR_REVIEW_REQUIRED"
        return result
    result["backup_not_live_db"] = True
    try:
        # Backups must be made with SQLite's online backup API, not a file
        # copy of a live WAL database. This cannot be attested programmatically.
        uri = backup.resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True, timeout=2.0)) as connection:
            connection.execute("PRAGMA query_only=ON")
            check = connection.execute("PRAGMA quick_check(1)").fetchone()
            result["sqlite_quick_check"] = str(check[0]) if check else "NO_RESULT"
            if result["sqlite_quick_check"] != "ok":
                result["state"] = "SQLITE_INTEGRITY_NOT_OK"
                return result
            tables = {r[0] for r in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
            if not REQUIRED_TABLES.issubset(tables):
                result["state"] = "REQUIRED_SEC_TABLES_MISSING"
                return result
            cols = {r[1] for r in connection.execute(
                "PRAGMA table_info(fundamental_facts_source)"
            )}
            if not {"source", "security_id"}.issubset(cols):
                result["state"] = "SEC_FACT_SCHEMA_MISSING_COLUMNS"
                return result
            result["sec_fact_count"] = int(connection.execute(
                "SELECT COUNT(*) FROM fundamental_facts_source WHERE source=?",
                ("SEC_EDGAR",),
            ).fetchone()[0])
            result["sec_security_count"] = int(connection.execute(
                "SELECT COUNT(DISTINCT security_id) FROM fundamental_facts_source WHERE source=?",
                ("SEC_EDGAR",),
            ).fetchone()[0])
            result["state"] = "BACKUP_SEC_COUNTS_READ_ONLY"
    except (sqlite3.Error, OSError, ValueError):
        result["state"] = "BACKUP_UNREADABLE_OR_INVALID"
    return result


def audit(
    runtime_root: Path,
    *, backup_db: Path | None = None,
    operator_import_stopped: bool = False,
    operator_online_backup_confirmed: bool = False,
    verify_zip_crc: bool = False,
) -> dict:
    """Offline evidence check; does not certify original SEC acceptance times."""
    root = Path(runtime_root).expanduser()
    phase0 = phase0_report(root, environ={})
    report: dict = {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "BLOCKED",
        "phase0_status": phase0["status"],
        "legacy_import_process_state_verified_by_tool": False,
        "operator_import_stopped_confirmed": operator_import_stopped,
        "online_backup_created_by_operator_confirmed": operator_online_backup_confirmed,
        "archive": {"state": "NOT_INSPECTED"},
        "backup": {"state": "NOT_INSPECTED"},
        "checkpoints": {},
        "blockers": [],
        "phase1_technical_gate_passed": False,
        "phase1_full_sec_coverage_certified": False,
        "original_sec_accepted_at_verified": False,
        "wf9_activated": False,
        "no_data_or_source_db_modified": True,
    }
    if phase0["status"] != "EVIDENCE_ONLY_NOT_CERTIFIED":
        report["blockers"].append("PHASE0_RUNTIME_MISSING_OR_UNSAFE")
        return report
    sec = phase0["sec"]
    progress = sec["instrumented_progress"]
    report["checkpoints"] = progress
    if sec["instrumented_import_lock"] != "NOT_FOUND":
        report["blockers"].append("SEC_IMPORT_LOCK_PRESENT_OR_UNTRUSTED")
    if sec["companyfacts_partial_zip"] != "NOT_FOUND":
        report["blockers"].append("SEC_ARCHIVE_PARTIAL_PRESENT_OR_UNTRUSTED")
    if not operator_import_stopped:
        report["blockers"].append("OPERATOR_MUST_VERIFY_LEGACY_AND_MODERN_IMPORTER_STOPPED")
    if report["blockers"]:
        report["status"] = "BLOCKED_IMPORT_RUNNING_OR_OPERATOR_UNCONFIRMED"
        return report

    if sec["companyfacts_zip"] != "FILE_PRESENT_UNVERIFIED":
        report["blockers"].append("SEC_COMPANYFACTS_ZIP_NOT_PRESENT")
        return report

    report["archive"] = _archive_inventory(
        root / "bulk" / "sec" / "companyfacts.zip",
        verify_crc=verify_zip_crc,
    )
    archive = report["archive"]
    if archive["state"] not in ("ZIP_CRC_VERIFIED", "ZIP_CENTRAL_DIRECTORY_ONLY"):
        report["blockers"].append("SEC_ARCHIVE_INVALID")
        return report
    if not archive["crc_checked"]:
        report["blockers"].append("SEC_ZIP_MEMBER_CRC_NOT_CHECKED")

    if progress["state"] != "INSTRUMENTED_IMPORT_FINISHED_UNVERIFIED":
        report["blockers"].append("SEC_IMPORT_FINISH_NOT_INDEPENDENTLY_PROVEN")
    elif (progress.get("entries_total") != archive["member_count"]
          or progress.get("entries_scanned") != archive["member_count"]):
        report["blockers"].append("SEC_IMPORT_CHECKPOINT_ARCHIVE_MEMBER_MISMATCH")

    if not operator_online_backup_confirmed:
        report["blockers"].append("OPERATOR_MUST_CONFIRM_SQLITE_ONLINE_BACKUP")
        report["status"] = "AWAITING_VERIFIED_ONLINE_BACKUP"
        return report
    live = root / "data" / "runtime" / "operational.db"
    report["backup"] = _backup_inventory(backup_db, live)
    backup = report["backup"]
    if backup["state"] != "BACKUP_SEC_COUNTS_READ_ONLY":
        report["blockers"].append("SQLITE_ONLINE_BACKUP_MISSING_OR_INVALID")
    elif progress["state"] == "INSTRUMENTED_IMPORT_FINISHED_UNVERIFIED":
        saved = _checkpoint_import_counts(
            root / "bulk" / "sec" / "companyfacts-progress.json"
        )
        report["imported_counts_from_checkpoint"] = saved
        inserted = saved["facts_written_this_run"]
        saved_issuers = saved["matched_issuers_saved"]
        if inserted is None or saved_issuers is None:
            report["blockers"].append("SEC_CHECKPOINT_SAVE_COUNTS_MISSING")
        elif inserted == 0 or saved_issuers == 0:
            report["blockers"].append("SEC_CHECKPOINT_ZERO_IMPORTED_RECORDS")
        else:
            if backup["sec_fact_count"] < inserted:
                report["blockers"].append("BACKUP_SEC_FACT_COUNT_BELOW_IMPORT_CHECKPOINT")
            if backup["sec_security_count"] < saved_issuers:
                report["blockers"].append("BACKUP_SEC_ISSUERS_BELOW_IMPORT_CHECKPOINT")
    if backup["state"] == "BACKUP_SEC_COUNTS_READ_ONLY" and (
        backup["sec_fact_count"] <= 0 or backup["sec_security_count"] <= 0
    ):
        report["blockers"].append("SEC_BACKUP_HAS_NO_FACTS_OR_ISSUERS")
    if report["blockers"]:
        report["status"] = "BLOCKED_PARTIAL_OR_UNVERIFIED_SEC_EVIDENCE"
    else:
        report["status"] = "PHASE1_TECHNICAL_EVIDENCE_RECONCILED_REVIEW_REQUIRED"
        report["phase1_technical_gate_passed"] = True
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--backup-db", type=Path)
    parser.add_argument("--operator-import-stopped", action="store_true",
                        help="Confirm with Windows Task Manager BEFORE checking ZIP or DB")
    parser.add_argument("--operator-online-backup-confirmed", action="store_true",
                        help="Confirm standalone SQLite online backup, not live file copy")
    parser.add_argument("--verify-zip-crc", action="store_true",
                        help="After import stopped, read/decompress each ZIP member; substantial disk I/O")
    args = parser.parse_args(argv)
    report = audit(
        args.runtime_root, backup_db=args.backup_db,
        operator_import_stopped=args.operator_import_stopped,
        operator_online_backup_confirmed=args.operator_online_backup_confirmed,
        verify_zip_crc=args.verify_zip_crc,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["phase1_technical_gate_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
