from __future__ import annotations

"""Daily, quota-conservative historical US listing-status ingestion.

- Source: existing Alpha Vantage LISTING_STATUS parser and SecurityRepository.
- Uses user's real S153_RUNTIME_ROOT; will not create an empty operational DB.
- Per UTC calendar day, reserves request budget BEFORE each provider request.
  This tracks requests from THIS tool only, not other software/API accounts.
- Skips already stored months, never overwrites them; failure stops immediately.
- Lock prevents overlapping runs. Scheduled Windows task is opt-in separately.
- This is listing-membership collection, NOT independent PIT certification.
"""
import argparse
import asyncio
from contextlib import closing
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
from uuid import uuid4

from app.bootstrap import AppContainer
from data.providers.alpha_vantage_pit_universe import AlphaVantagePitUniverseProvider
from data.providers.massive_universe import MassiveUniverseProvider
from data.repositories.security_repository import SecurityRepository
from scripts.sync_free_pit_universe import _load_snapshot, month_end_dates

SCHEMA = "MERIDYEN_DAILY_PIT_SYNC_V1"
DEFAULT_START = date(2013, 1, 1)
DEFAULT_END = date(2024, 12, 31)
DEFAULT_LIMIT = 20  # Below free 25/day; 5-request safety margin.
MAX_DAILY_LIMIT = 20


def _now():
    return datetime.now(timezone.utc)


def _write_atomic(path: Path, value: dict) -> None:
    temp = path.with_name("." + path.name + "." + uuid4().hex + ".tmp")
    try:
        with temp.open("x", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _read_budget(path: Path, today: str) -> dict:
    if not path.exists():
        return {"schema": SCHEMA, "utc_date": today, "attempts": 0}
    if path.is_symlink():
        raise ValueError("Request budget state cannot be a symlink")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise ValueError("Existing quota state is invalid; no API calls made")
    old_date = date.fromisoformat(str(data.get("utc_date")))
    count = data.get("attempts")
    if type(count) is not int or not 0 <= count <= MAX_DAILY_LIMIT:
        raise ValueError("Invalid quota attempt count; no API calls made")
    if old_date > date.fromisoformat(today):
        raise ValueError("System UTC clock moved backwards; API use blocked")
    if old_date < date.fromisoformat(today):
        return {"schema": SCHEMA, "utc_date": today, "attempts": 0}
    return data


def _reserve_request(path: Path, state: dict, limit: int) -> dict | None:
    if state["attempts"] >= limit:
        return None
    # Reserve BEFORE the HTTP call, preserving the cap through crashes.
    next_state = {**state, "attempts": state["attempts"] + 1}
    _write_atomic(path, next_state)
    return next_state


def _has_months(conn_path: Path, snapshots: list[date]) -> dict[str, int]:
    with closing(sqlite3.connect(conn_path.resolve().as_uri() + "?mode=ro", uri=True)) as con:
        available = set(row[0] for row in con.execute(
            """SELECT DISTINCT snapshot_date
               FROM universe_snapshot_membership
               WHERE source='ALPHAVANTAGE_PIT' AND
               snapshot_date BETWEEN ? AND ?""",
            (snapshots[0].isoformat(), snapshots[-1].isoformat()),
        ))
    return {"present": len(available), "missing": len(snapshots) - len(available)}


async def run_daily(
    runtime_root: Path, *, start: date = DEFAULT_START, end: date = DEFAULT_END,
    daily_limit: int = DEFAULT_LIMIT, repo_root: Path | None = None,
    current_time: datetime | None = None,
) -> dict:
    if not 1 <= daily_limit <= MAX_DAILY_LIMIT:
        raise ValueError("Daily cap must be between 1 and 20 requests")
    snapshots = month_end_dates(start, end)
    if not snapshots:
        raise ValueError("No complete month ends in date window")
    root = Path(runtime_root).expanduser().resolve()
    database = root / "data" / "runtime" / "operational.db"
    if not database.is_file() or database.is_symlink():
        raise ValueError("Actual M10 operational.db missing; refusing to create a new database")
    code_root = Path(repo_root or Path(__file__).resolve().parents[1]).resolve()
    if not (code_root / "config" / "app.yaml").is_file():
        raise ValueError("M10 checkout config missing")
    # Set before AppContainer() reads the runtime path.
    os.environ["S153_RUNTIME_ROOT"] = str(root)
    storage = root / "data" / "runtime" / "pit_daily_sync"
    storage.mkdir(parents=True, exist_ok=True)
    lock = storage / "daily.lock"
    try:
        fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise ValueError("Another PIT sync holds daily.lock; never delete an active lock") from exc
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(json.dumps({"started": _now().isoformat(), "pid": os.getpid()}) + "\n")

        now = current_time or _now()
        if now.tzinfo is None:
            raise ValueError("Calendar time must have timezone")
        utc_day = now.astimezone(timezone.utc).date().isoformat()
        state_path = storage / "utc_request_budget.json"
        state = _read_budget(state_path, utc_day)

        # Load .env without disclosing key in logs or stdout.
        app = AppContainer(code_root)
        app.initialize()
        try:
            provider = AlphaVantagePitUniverseProvider()
            massive = MassiveUniverseProvider()
            if not provider.configured:
                raise ValueError("Missing ALPHAVANTAGE_API_KEY in M10 local .env")
            repository = SecurityRepository(app.sqlite)
            successful = 0
            skipped = 0
            status = "COMPLETE_LISTINGS_NOT_PIT_CERTIFIED"
            stopped_at = None
            fail_type = None
            for as_of in snapshots:
                if repository.universe_as_of(as_of):
                    skipped += 1
                    continue
                new_state = _reserve_request(state_path, state, daily_limit)
                if new_state is None:
                    status = "DAILY_REQUEST_BUDGET_REACHED"
                    stopped_at = as_of.isoformat()
                    break
                state = new_state
                try:
                    records, source = await _load_snapshot(
                        as_of=as_of, mode="ALPHAVANTAGE",
                        alpha=provider, massive=massive,
                    )
                    if source != "ALPHAVANTAGE_PIT" or not records:
                        raise ValueError("Unexpected or empty PIT listing source")
                    repository.bulk_upsert_historical_snapshot(records, snapshot_date=as_of)
                except Exception as exc:
                    status = "PROVIDER_STOPPED_REVIEW_ACCOUNT_OR_QUOTA"
                    stopped_at = as_of.isoformat()
                    # Do not include API key, URL, vendor payload, or private rows.
                    fail_type = type(exc).__name__
                    break
                successful += 1
            coverage = _has_months(database, snapshots)
        finally:
            app.close()

        report = {
            "schema": SCHEMA,
            "status": status,
            "utc_date": utc_day,
            "window": {"start": start.isoformat(), "end": end.isoformat()},
            "monthly_snapshots_target": len(snapshots),
            "monthly_snapshots_present": coverage["present"],
            "monthly_snapshots_missing": coverage["missing"],
            "snapshots_downloaded_this_run": successful,
            "existing_months_skipped": skipped,
            "api_requests_recorded_today_by_this_tool": state["attempts"],
            "daily_limit_for_this_tool": daily_limit,
            "first_missing_or_failed_date": stopped_at,
            "provider_failure_class": fail_type,
            "provider": "ALPHAVANTAGE_PIT",
            "real_api_quota_not_independently_known": True,
            "other_clients_api_calls_not_counted": True,
            "pit_corporate_actions_fundamentals_prices_certified": False,
            "wf9_activated": False,
        }
        report_file = storage / "latest_status.json"
        _write_atomic(report_file, report)
        # Append a minimal local audit trail. No URLs or credentials.
        with (storage / "history.jsonl").open("a", encoding="utf-8") as log:
            log.write(json.dumps(report, ensure_ascii=False) + "\n")
        report["report_path"] = str(report_file)
        return report
    finally:
        # Only the invocation that won exclusive creation deletes its lock.
        lock.unlink(missing_ok=True)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--runtime-root", type=Path, required=True)
    p.add_argument("--start", type=date.fromisoformat, default=DEFAULT_START)
    p.add_argument("--end", type=date.fromisoformat, default=DEFAULT_END)
    p.add_argument("--daily-limit", type=int, default=DEFAULT_LIMIT)
    p.add_argument("--status-only", action="store_true", help="Read latest report without API calls")
    args = p.parse_args()
    root = args.runtime_root.expanduser().resolve()
    file = root / "data" / "runtime" / "pit_daily_sync" / "latest_status.json"
    if args.status_only:
        if not file.is_file():
            p.exit(2, "No daily PIT status yet. Task has not run.\n")
        print(file.read_text(encoding="utf-8"))
        return 0
    try:
        report = asyncio.run(run_daily(root, start=args.start, end=args.end, daily_limit=args.daily_limit))
    except (OSError, ValueError, sqlite3.Error, json.JSONDecodeError) as exc:
        p.exit(2, "DAILY_PIT_BLOCKED: " + type(exc).__name__ + ": " + str(exc) + "\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] != "PROVIDER_STOPPED_REVIEW_ACCOUNT_OR_QUOTA" else 2


if __name__ == "__main__":
    raise SystemExit(main())
