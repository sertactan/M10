from __future__ import annotations

"""Phase 2: additional bounded READ ONLY M10 operational diagnostics.

No provider calls, no load_local_env, no SQLiteStore, no process polling, no
writing, no secrets or provider error messages. Existing report files are
local observations: they cannot independently attest WF9 activation.
"""
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sqlite3

ALLOWED_PHASE13 = {
    "BLOCKED_DB_NOT_FOUND", "BLOCKED_SCHEMA", "PREFLIGHT_BLOCKED",
    "PREFLIGHT_READY_NOT_ACTIVATED", "BLOCKED_DIAGNOSTIC_ERROR",
}
MAX_JSON_BYTES = 200_000
MAX_ERROR_EVENTS = 5


@dataclass(frozen=True)
class Phase2Diagnostics:
    pit_year_coverage: tuple[tuple[str, int], ...]
    adjusted_sources: tuple[tuple[str, str, str, int, int], ...]
    provider_states: tuple[tuple[str, str, int, str], ...]
    recent_provider_failures: tuple[tuple[str, str, bool], ...]
    queued_tasks: tuple[tuple[str, int], ...]
    sec_archive_status: str
    sec_archive_size_mb: float | None
    sec_archive_modified_utc: str | None
    sec_import_completion_verified: bool
    wf9_report_status: str
    wf9_report_generated_at_utc: str | None
    wf9_report_blockers: tuple[str, ...]
    wf9_report_stale: bool | None
    daily_pit_requests_used: int | None
    daily_pit_requests_limit: int | None
    diagnostic_notes: tuple[str, ...]


def _safe_token(value: object) -> str:
    """No user/private payload or free-form provider error details in UI."""
    clean = str(value or "").strip().upper()
    return clean[:64] if re.fullmatch(r"[A-Z0-9_./:-]{1,64}", clean) else "UNRECOGNIZED"


def _read_local_json(file: Path, expected_schema: str) -> tuple[str, dict | None]:
    if file.is_symlink() or not file.is_file():
        return ("MISSING" if not file.is_symlink() else "INVALID_SYMLINK"), None
    if file.stat().st_size > MAX_JSON_BYTES:
        return "INVALID_OVERSIZE", None
    try:
        obj = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return "INVALID_JSON", None
    if not isinstance(obj, dict) or obj.get("schema") != expected_schema:
        return "INVALID_SCHEMA", None
    return "OK", obj


def _timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None or dt.utcoffset() is None:
        return None
    return dt.astimezone(timezone.utc)


def phase2_diagnostics(
    conn: sqlite3.Connection | None,
    tables: set[str],
    pit_dates: set[str],
    runtime_root: Path,
    now: datetime,
) -> Phase2Diagnostics:
    years = tuple(
        (str(year), len([s for s in pit_dates if s.startswith(f"{year}-")]))
        for year in range(2013, 2025)
    )
    sources: list[tuple[str, str, str, int, int]] = []
    states: list[tuple[str, str, int, str]] = []
    failures: list[tuple[str, str, bool]] = []
    queue: list[tuple[str, int]] = []
    notes: list[str] = []

    if conn is not None and "price_series_registry" in tables:
        for provider, first, last, series, bars in conn.execute(
            """SELECT source,MIN(start_date),MAX(end_date),COUNT(*),SUM(row_count)
               FROM price_series_registry
               WHERE adjustment_status IN (
                   'DUAL_RAW_ADJUSTED','PROVIDER_ADJUSTED','ADJUSTED_ONLY'
               )
               GROUP BY source ORDER BY source LIMIT 25"""
        ):
            sources.append((_safe_token(provider), str(first), str(last),
                            int(series or 0), int(bars or 0)))
        notes.append(
            "Price source spans show MIN/MAX across series, NOT full "
            "per-security date coverage or verified delisting payout."
        )

    if conn is not None and "provider_health_state" in tables:
        for provider, circuit, n, attempted in conn.execute(
            """SELECT provider,circuit_state,consecutive_failures,last_attempt_at
               FROM provider_health_state ORDER BY provider LIMIT 30"""
        ):
            states.append((_safe_token(provider), _safe_token(circuit),
                           int(n or 0), str(attempted or "UNKNOWN")[:32]))
    else:
        notes.append("No persisted API health state available; absence is NOT healthy API.")

    if conn is not None and "provider_health_events" in tables:
        # Always inspect only the newest 100 events. Searching for failures
        # with WHERE success=0 could scan an unbounded healthy event history.
        for provider, when, rate_limited, success in conn.execute(
            """SELECT provider,observed_at,rate_limited,success
               FROM provider_health_events
               ORDER BY event_id DESC LIMIT 100"""
        ):
            if not success:
                failures.append((_safe_token(provider), str(when)[:32], bool(rate_limited)))
                if len(failures) >= MAX_ERROR_EVENTS:
                    break
    if conn is not None and "background_sync_tasks" in tables:
        for status, n in conn.execute(
            """SELECT status,COUNT(*) FROM background_sync_tasks
               GROUP BY status ORDER BY status LIMIT 20"""
        ):
            queue.append((_safe_token(status), int(n)))

    archive_dir = runtime_root / "bulk" / "sec"
    finished = archive_dir / "companyfacts.zip"
    partial = archive_dir / "companyfacts.zip.part"
    archive_status = "SEC_ARCHIVE_NOT_FOUND"
    archive_size = None
    archive_mtime = None
    for file, label in ((partial, "SEC_ARCHIVE_PARTIAL_DOWNLOAD"),
                        (finished, "SEC_ARCHIVE_PRESENT_IMPORT_UNVERIFIED")):
        if file.is_symlink():
            archive_status = "SEC_ARCHIVE_SYMLINK_UNTRUSTED"
            break
        if file.is_file():
            stat = file.stat()
            archive_status = label
            archive_size = round(stat.st_size / (1024 * 1024), 1)
            archive_mtime = datetime.fromtimestamp(
                stat.st_mtime, tz=timezone.utc
            ).isoformat()
            # A complete zip does not prove the SEC Companyfacts importer has
            # finished processing its millions of rows.
            if label == "SEC_ARCHIVE_PARTIAL_DOWNLOAD":
                break

    wf9_file = runtime_root / "data" / "runtime" / "phase13_readiness" / "PHASE13_READINESS.json"
    wf9_read_state, wf9 = _read_local_json(
        wf9_file, "MERIDYEN_PHASE13_READINESS_V1"
    )
    wf9_status = ("NO_LOCAL_WF9_PREFLIGHT_REPORT" if wf9_read_state == "MISSING"
                  else "INVALID_LOCAL_WF9_REPORT" if wf9_read_state != "OK"
                  else "UNKNOWN")
    wf9_blockers: tuple[str, ...] = ()
    wf9_generated = None
    stale: bool | None = None
    if wf9 is not None:
        candidate = wf9.get("status")
        wf9_status = candidate if candidate in ALLOWED_PHASE13 else "INVALID_WF9_STATUS"
        generated = _timestamp(wf9.get("generated_at"))
        if generated is None:
            wf9_status = "INVALID_WF9_TIMESTAMP"
        else:
            wf9_generated = generated.isoformat()
            age = now.astimezone(timezone.utc) - generated
            stale = age > timedelta(hours=24) or age < -timedelta(minutes=5)
        raw_blockers = wf9.get("blockers")
        if isinstance(raw_blockers, list):
            wf9_blockers = tuple(_safe_token(x) for x in raw_blockers[:12])
        else:
            wf9_status = "INVALID_WF9_BLOCKERS"
        notes.append(
            "WF9 preflight JSON is a LOCAL cached diagnostic, not proof "
            "of a completed, activated or successful historical backtest."
        )

    daily_file = runtime_root / "data" / "runtime" / "pit_daily_sync" / "latest_status.json"
    daily_state, daily = _read_local_json(daily_file, "MERIDYEN_DAILY_PIT_SYNC_V1")
    used = limit = None
    if daily_state == "OK" and daily is not None:
        u = daily.get("api_requests_recorded_today_by_this_tool")
        l = daily.get("daily_limit_for_this_tool")
        if type(u) is int and type(l) is int and 0 <= u <= 1000 and 0 < l <= 1000:
            used, limit = u, l
    notes.append(
        "SEC import stage cannot be inferred from zip size; refresh fact "
        "count manually to observe change, not process completion."
    )
    notes.append(
        "Provider health logs cover only instrumented M10 requests; "
        "no API keys or raw provider error messages are displayed."
    )
    return Phase2Diagnostics(
        pit_year_coverage=years,
        adjusted_sources=tuple(sources),
        provider_states=tuple(states),
        recent_provider_failures=tuple(failures),
        queued_tasks=tuple(queue),
        sec_archive_status=archive_status,
        sec_archive_size_mb=archive_size,
        sec_archive_modified_utc=archive_mtime,
        sec_import_completion_verified=False,
        wf9_report_status=wf9_status,
        wf9_report_generated_at_utc=wf9_generated,
        wf9_report_blockers=wf9_blockers,
        wf9_report_stale=stale,
        daily_pit_requests_used=used,
        daily_pit_requests_limit=limit,
        diagnostic_notes=tuple(notes),
    )
