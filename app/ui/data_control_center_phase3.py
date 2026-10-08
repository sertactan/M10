from __future__ import annotations

"""Bounded, read-only Phase3 diagnostics for installed M10 Data Control Center.

Never certifies completion or start safety from absence of a lock: older SEC
importers might be running without the new telemetry. Never reads API keys.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3

from app.sec_import_progress import SCHEMA, PROGRESS_FILE, LOCK_FILE
from app.ui.data_control_center_phase2 import _read_local_json, _timestamp, _safe_token

MAX_SEC_SAMPLE = 250
ROWID_WINDOW = 5000


@dataclass(frozen=True)
class Phase3Diagnostics:
    sec_checkpoint_status: str
    sec_checkpoint_stage: str | None
    sec_checkpoint_updated_utc: str | None
    sec_checkpoint_stale: bool | None
    sec_lock_present: bool
    sec_entries_scanned: int | None
    sec_entries_total: int | None
    sec_issuers_saved: int | None
    sec_facts_written_this_run: int | None
    sec_import_verified_complete: bool
    sec_quality_rows_sampled: int
    sec_quality_missing_accepted_at: int
    sec_quality_missing_accession: int
    sec_quality_invalid_availability: int
    sec_quality_time_order_conflicts: int
    readiness_control: str
    notes: tuple[str, ...]


def _count_nonnegative(data: dict, name: str) -> int | None:
    value = data.get(name)
    return value if type(value) is int and 0 <= value <= 1_000_000_000 else None


def phase3_diagnostics(
    conn: sqlite3.Connection | None,
    tables: set[str],
    runtime_root: Path,
    now: datetime,
) -> Phase3Diagnostics:
    archive_dir = runtime_root / "bulk/sec"
    lock = archive_dir / LOCK_FILE
    locked = lock.exists() or lock.is_symlink()
    progress_state, progress = _read_local_json(archive_dir / PROGRESS_FILE, SCHEMA)
    status = (
        "NO_INSTRUMENTED_SEC_RUN" if progress_state == "MISSING"
        else "INVALID_SEC_CHECKPOINT" if progress_state != "OK"
        else "PROGRESS_CHECKPOINT_PRESENT"
    )
    stage = last = None
    stale = None
    scanned = total = issuers = facts = None
    if progress is not None:
        candidate = progress.get("stage")
        stage = candidate if candidate in {
            "STARTING", "IMPORTING", "FINALIZING", "FAILED", "FINISHED"
        } else "INVALID_STAGE"
        timestamp = _timestamp(progress.get("updated_utc"))
        if timestamp is not None:
            last = timestamp.isoformat()
            delta = now.astimezone(timezone.utc) - timestamp
            stale = delta > timedelta(minutes=10) or delta < -timedelta(minutes=5)
        else:
            status = "INVALID_CHECKPOINT_TIMESTAMP"
        scanned = _count_nonnegative(progress, "entries_scanned")
        total = _count_nonnegative(progress, "entries_total")
        issuers = _count_nonnegative(progress, "matched_issuers_saved")
        facts = _count_nonnegative(progress, "facts_written_this_run")
        if total is not None and scanned is not None and scanned > total:
            status = "INVALID_CHECKPOINT_COUNTS"
        # Authenticated provenance and SEC fact PIT quality are not verified.
        if stage == "FINISHED" and not locked and status == "PROGRESS_CHECKPOINT_PRESENT":
            status = "RUN_REPORTED_FINISHED_NOT_INDEPENDENTLY_VERIFIED"
        elif stage == "FAILED":
            status = "RUN_REPORTED_FAILED"
        elif locked:
            status = "LOCK_PRESENT_PROGRESS_ONLY"
    elif locked:
        status = "LOCK_PRESENT_NO_VALID_CHECKPOINT"

    sampled = no_acceptance = no_accession = invalid_available = order_conflicts = 0
    if conn is not None and "fundamental_facts_source" in tables:
        max_id = conn.execute(
            "SELECT MAX(rowid) FROM fundamental_facts_source"
        ).fetchone()[0]
        if max_id is not None:
            recent = conn.execute(
                """SELECT accepted_at,available_at,accession_number
                   FROM fundamental_facts_source
                   WHERE rowid BETWEEN ? AND ? AND source='SEC_EDGAR'
                   ORDER BY rowid DESC LIMIT ?""",
                (max(1, max_id - ROWID_WINDOW + 1), max_id, MAX_SEC_SAMPLE),
            )
            for accepted, available, accession in recent:
                sampled += 1
                if not accepted:
                    no_acceptance += 1
                if not accession:
                    no_accession += 1
                available_dt = _timestamp(available)
                if available_dt is None:
                    invalid_available += 1
                accepted_dt = _timestamp(accepted)
                if accepted_dt is not None and available_dt is not None and (
                    available_dt < accepted_dt
                ):
                    order_conflicts += 1

    reasons: list[str] = []
    if locked:
        reasons.append("LOCK_PRESENT: refuse another instrumented ZIP import.")
    elif progress is not None and stage in ("STARTING","IMPORTING","FINALIZING"):
        reasons.append(
            "INCOMPLETE_CHECKPOINT_NO_LOCK: legacy/crashed state uncertain; "
            "do not auto-restart or delete markers."
        )
    else:
        reasons.append(
            "LOCK_ABSENT_IS_NOT_CLEARANCE: legacy import processes lack this "
            "lock. Only launch after explicit operator confirmation."
        )
    reasons.append(
        "SEC sample is recent-rowid biased, bounded to 5000-row window; "
        "missing acceptance timestamps block original SEC PIT certification."
    )
    reasons.append(
        "No import, retry, cleanup, API call, DB mutation or WF9 promotion "
        "is possible from this diagnostic."
    )
    return Phase3Diagnostics(
        sec_checkpoint_status=status,
        sec_checkpoint_stage=stage,
        sec_checkpoint_updated_utc=last,
        sec_checkpoint_stale=stale,
        sec_lock_present=locked,
        sec_entries_scanned=scanned,
        sec_entries_total=total,
        sec_issuers_saved=issuers,
        sec_facts_written_this_run=facts,
        sec_import_verified_complete=False,
        sec_quality_rows_sampled=sampled,
        sec_quality_missing_accepted_at=no_acceptance,
        sec_quality_missing_accession=no_accession,
        sec_quality_invalid_availability=invalid_available,
        sec_quality_time_order_conflicts=order_conflicts,
        readiness_control=(
            "BLOCKED_ACTIVE_SEC_LOCK" if locked else
            "MANUAL_OPERATOR_CONFIRMATION_REQUIRED_LEGACY_UNDETECTABLE"
        ),
        notes=tuple(reasons),
    )
