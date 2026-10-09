from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import zipfile

from scripts.sec_companyfacts_phase1_audit import audit, _archive_inventory
from scripts.sec_massive_phase0_inventory import PROGRESS_SCHEMA


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "runtime"
    (root / "bulk" / "sec").mkdir(parents=True)
    (root / "data" / "runtime").mkdir(parents=True)
    return root


def _zip(root: Path, *, docs: int = 2) -> Path:
    path = root / "bulk" / "sec" / "companyfacts.zip"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for cik in range(1, docs + 1):
            z.writestr(f"CIK{cik:010d}.json", '{"entityName":"test"}')
    return path


def _checkpoint(root: Path, *, total: int = 2, scanned: int = 2,
                stage: str = "FINISHED", facts: int = 3, issuers: int = 2) -> None:
    payload = {
        "schema": PROGRESS_SCHEMA, "stage": stage,
        "entries_total": total, "entries_scanned": scanned,
        "complete_archive_processed": stage == "FINISHED" and scanned == total,
        "facts_written_this_run": facts, "matched_issuers_saved": issuers,
    }
    (root / "bulk" / "sec" / "companyfacts-progress.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def _sqlite_backup(root: Path, tmp_path: Path, *, facts: int = 3,
                   sec_issuers: int = 2) -> Path:
    live = root / "data" / "runtime" / "operational.db"
    with sqlite3.connect(live) as db:
        db.execute("CREATE TABLE security_master (security_id TEXT PRIMARY KEY, cik TEXT)")
        db.execute("CREATE TABLE fundamental_facts_source (security_id TEXT, source TEXT)")
        for idx in range(facts):
            security_id = str((idx % sec_issuers) + 1) if sec_issuers else str(idx + 1)
            db.execute("INSERT INTO fundamental_facts_source VALUES (?,?)",
                       (security_id, "SEC_EDGAR"))
    target = tmp_path / "sec_snapshot_backup.db"
    with sqlite3.connect(live) as source:
        with sqlite3.connect(target) as dest:
            source.backup(dest)
    return target


def _run(root: Path, *, backup: Path | None = None, crc: bool = True) -> dict:
    return audit(root, backup_db=backup, operator_import_stopped=True,
                 operator_online_backup_confirmed=True, verify_zip_crc=crc)


def test_default_guard_prevents_zip_and_sqlite_inspection(tmp_path: Path) -> None:
    root = _root(tmp_path)
    (root / "bulk" / "sec" / "companyfacts.zip").write_bytes(b"not zip")
    result = audit(root)
    assert result["status"] == "BLOCKED_IMPORT_RUNNING_OR_OPERATOR_UNCONFIRMED"
    assert result["archive"]["state"] == "NOT_INSPECTED"
    assert result["backup"]["state"] == "NOT_INSPECTED"
    assert result["phase1_technical_gate_passed"] is False


def test_lock_refuses_archive_and_db_read_even_with_operator_flag(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _zip(root)
    (root / "bulk" / "sec" / "companyfacts-import.lock").write_text("lock")
    result = audit(root, operator_import_stopped=True,
                   operator_online_backup_confirmed=True, verify_zip_crc=True)
    assert "SEC_IMPORT_LOCK_PRESENT_OR_UNTRUSTED" in result["blockers"]
    assert result["archive"]["state"] == "NOT_INSPECTED"
    assert result["backup"]["state"] == "NOT_INSPECTED"


def test_partial_archive_blocks_before_backup_or_zip_inspect(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _zip(root)
    (root / "bulk" / "sec" / "companyfacts.zip.part").write_bytes(b"partial")
    result = audit(root, operator_import_stopped=True,
                   operator_online_backup_confirmed=True)
    assert "SEC_ARCHIVE_PARTIAL_PRESENT_OR_UNTRUSTED" in result["blockers"]
    assert result["archive"]["state"] == "NOT_INSPECTED"


def test_valid_archive_without_crc_not_certified(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _zip(root)
    _checkpoint(root)
    backup = _sqlite_backup(root, tmp_path)
    result = _run(root, backup=backup, crc=False)
    assert result["archive"]["state"] == "ZIP_CENTRAL_DIRECTORY_ONLY"
    assert "SEC_ZIP_MEMBER_CRC_NOT_CHECKED" in result["blockers"]
    assert result["phase1_technical_gate_passed"] is False


def test_complete_fixture_crc_and_backup_evidence_only(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _zip(root)
    _checkpoint(root)
    backup = _sqlite_backup(root, tmp_path)
    result = _run(root, backup=backup)
    assert result["status"] == "PHASE1_TECHNICAL_EVIDENCE_RECONCILED_REVIEW_REQUIRED"
    assert result["phase1_technical_gate_passed"] is True
    assert result["phase1_full_sec_coverage_certified"] is False
    assert result["original_sec_accepted_at_verified"] is False
    assert result["wf9_activated"] is False
    assert result["archive"]["crc_checked"] is True
    assert result["backup"]["sec_fact_count"] == 3
    assert result["backup"]["sec_security_count"] == 2


def test_finished_counter_different_from_zip_blocks(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _zip(root)
    _checkpoint(root, total=5, scanned=5)
    backup = _sqlite_backup(root, tmp_path)
    result = _run(root, backup=backup)
    assert "SEC_IMPORT_CHECKPOINT_ARCHIVE_MEMBER_MISMATCH" in result["blockers"]


def test_missing_progress_with_legacy_import_never_promotes(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _zip(root)
    backup = _sqlite_backup(root, tmp_path)
    result = _run(root, backup=backup)
    assert "SEC_IMPORT_FINISH_NOT_INDEPENDENTLY_PROVEN" in result["blockers"]
    assert result["phase1_technical_gate_passed"] is False


def test_live_db_refused_even_when_operator_claims_backup(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _zip(root)
    _checkpoint(root)
    _sqlite_backup(root, tmp_path)
    live = root / "data" / "runtime" / "operational.db"
    result = _run(root, backup=live)
    assert result["backup"]["state"] == "REFUSED_LIVE_DATABASE"
    assert result["phase1_technical_gate_passed"] is False


def test_sqlite_backup_sidecar_refused(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _zip(root)
    _checkpoint(root)
    backup = _sqlite_backup(root, tmp_path)
    Path(str(backup) + "-wal").write_bytes(b"stale")
    result = _run(root, backup=backup)
    assert result["backup"]["state"] == "BACKUP_HAS_SQLITE_SIDECAR_REVIEW_REQUIRED"


def test_import_counts_above_backup_counts_block(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _zip(root)
    _checkpoint(root, facts=50, issuers=2)
    backup = _sqlite_backup(root, tmp_path)
    result = _run(root, backup=backup)
    assert "BACKUP_SEC_FACT_COUNT_BELOW_IMPORT_CHECKPOINT" in result["blockers"]


def test_zero_import_counts_fail_closed(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _zip(root)
    _checkpoint(root, facts=0, issuers=0)
    backup = _sqlite_backup(root, tmp_path)
    result = _run(root, backup=backup)
    assert "SEC_CHECKPOINT_ZERO_IMPORTED_RECORDS" in result["blockers"]


def test_invalid_zip_is_rejected_without_extraction(tmp_path: Path) -> None:
    root = _root(tmp_path)
    bad = root / "bulk" / "sec" / "companyfacts.zip"
    bad.write_bytes(b"corrupt")
    assert _archive_inventory(bad, verify_crc=True)["state"] == "ZIP_UNREADABLE_OR_CORRUPT"


def test_duplicate_cik_entries_are_rejected(tmp_path: Path) -> None:
    root = _root(tmp_path)
    path = root / "bulk" / "sec" / "companyfacts.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("CIK0000000001.json", "{}")
        archive.writestr("CIK0000000001.JSON", "{}")
    assert _archive_inventory(path)["state"] == "MISSING_OR_DUPLICATE_CIK_DOCUMENTS"


def test_symlink_archive_refused(tmp_path: Path) -> None:
    root = _root(tmp_path)
    outside = tmp_path / "outside.zip"
    with zipfile.ZipFile(outside, "w") as archive:
        archive.writestr("CIK0000000001.json", "{}")
    (root / "bulk" / "sec" / "companyfacts.zip").symlink_to(outside)
    result = audit(root, operator_import_stopped=True,
                   operator_online_backup_confirmed=True)
    assert "SEC_COMPANYFACTS_ZIP_NOT_PRESENT" in result["blockers"]
    assert result["archive"]["state"] == "NOT_INSPECTED"


def test_archived_missing_backup_not_promoted(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _zip(root)
    _checkpoint(root)
    result = _run(root, backup=None)
    assert result["backup"]["state"] == "BACKUP_NOT_PROVIDED"
    assert "SQLITE_ONLINE_BACKUP_MISSING_OR_INVALID" in result["blockers"]
