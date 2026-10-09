from __future__ import annotations

import json
from pathlib import Path

from scripts.sec_massive_phase0_inventory import build_report, PROGRESS_SCHEMA


def _runtime(tmp_path: Path) -> Path:
    root = tmp_path / "runtime"
    root.mkdir()
    return root


def _progress(root: Path, **overrides) -> Path:
    directory = root / "bulk" / "sec"
    directory.mkdir(parents=True, exist_ok=True)
    record = {
        "schema": PROGRESS_SCHEMA, "stage": "IMPORTING",
        "entries_total": 100, "entries_scanned": 50,
        "complete_archive_processed": False,
    }
    record.update(overrides)
    path = directory / "companyfacts-progress.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    return path


def test_missing_runtime_never_claims_success(tmp_path: Path) -> None:
    report = build_report(tmp_path / "missing", {})
    assert report["status"] == "BLOCKED_RUNTIME_NOT_CONFIRMED"
    assert report["wf9_activated"] is False


def test_existing_zip_and_db_never_means_sec_complete(tmp_path: Path) -> None:
    root = _runtime(tmp_path)
    archive = root / "bulk" / "sec"
    archive.mkdir(parents=True)
    (archive / "companyfacts.zip").write_bytes(b"not-real-zip")
    db = root / "data" / "runtime"
    db.mkdir(parents=True)
    (db / "operational.db").write_bytes(b"not-real-sqlite")
    report = build_report(root, {})
    assert report["status"] == "EVIDENCE_ONLY_NOT_CERTIFIED"
    assert report["sec"]["companyfacts_zip"] == "FILE_PRESENT_UNVERIFIED"
    assert report["sec"]["full_fundamentals_loaded"] == "NOT_VERIFIED"
    assert report["safe_to_start_second_import"] is False
    assert report["storage"]["sqlite_opened"] is False


def test_finished_checkpoint_still_not_independently_verified(tmp_path: Path) -> None:
    root = _runtime(tmp_path)
    _progress(root, stage="FINISHED", entries_scanned=100,
              complete_archive_processed=True)
    report = build_report(root, {})
    checkpoint = report["sec"]["instrumented_progress"]
    assert checkpoint["state"] == "INSTRUMENTED_IMPORT_FINISHED_UNVERIFIED"
    assert checkpoint["run_finish_asserted"] is True
    assert checkpoint["import_completed"] is False
    assert report["pit_independently_certified"] is False
    assert report["sec_import_running"] == "UNKNOWN"


def test_invalid_finished_counters_fail_closed(tmp_path: Path) -> None:
    root = _runtime(tmp_path)
    _progress(root, stage="FINISHED", entries_total=100, entries_scanned=101,
              complete_archive_processed=True)
    report = build_report(root, {})
    assert report["sec"]["instrumented_progress"]["state"] == "INVALID_FIELDS"
    assert report["safe_to_start_second_import"] is False


def test_progress_symlink_rejected(tmp_path: Path) -> None:
    root = _runtime(tmp_path)
    directory = root / "bulk" / "sec"
    directory.mkdir(parents=True)
    target = tmp_path / "untrusted.json"
    target.write_text("{}", encoding="utf-8")
    (directory / "companyfacts-progress.json").symlink_to(target)
    report = build_report(root, {})
    assert report["sec"]["instrumented_progress"]["state"] == "UNSAFE_SYMLINK"


def test_bounded_progress_file(tmp_path: Path) -> None:
    root = _runtime(tmp_path)
    directory = root / "bulk" / "sec"
    directory.mkdir(parents=True)
    (directory / "companyfacts-progress.json").write_bytes(b"x" * 200001)
    report = build_report(root, {})
    assert report["sec"]["instrumented_progress"]["state"] == "INVALID_OVERSIZE"


def test_secret_values_never_in_report(tmp_path: Path) -> None:
    root = _runtime(tmp_path)
    secrets = {
        "MASSIVE_API_KEY": "SECRET_MASSIVE_DO_NOT_LOG_123",
        "ALPHAVANTAGE_API_KEY": "SECRET_ALPHA_DO_NOT_LOG_456",
        "SEC_USER_AGENT": "Secret Name secret-email@example.net",
    }
    report = build_report(root, secrets)
    serialized = json.dumps(report)
    assert report["massive"]["massive_process_environment_configured"] is True
    assert report["massive"]["massive_historical_entitlement_verified"] is False
    assert all(secret not in serialized for secret in secrets.values())
    assert report["massive"]["local_dotenv_examined"] is False


def test_no_configured_key_is_not_entitlement_verdict(tmp_path: Path) -> None:
    root = _runtime(tmp_path)
    report = build_report(root, {})
    assert report["massive"]["massive_process_environment_configured"] is False
    assert report["massive"]["historical_price_data_loaded"] == "NOT_VERIFIED"
    assert report["pit_snapshots"]["actual"] is None
    assert report["pit_snapshots"]["required"] == 144
