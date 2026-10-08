from __future__ import annotations

"""Read-only M10 Data Control Center observations.

Safe while a separate SEC Companyfacts importer is writing: SQLite opens
mode=ro, query_only, no schema initialization, no provider/network calls,
no model execution, no background tasks and no database creation.
Counts are observations, NEVER certification of PIT/WF9/ML training.
"""
from calendar import monthrange
from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import sys

from core.runtime.logging import runtime_state_dir


@dataclass(frozen=True)
class ControlCenterSnapshot:
    observed_at: datetime
    source: str
    pit_present: int | None
    pit_target: int
    pit_missing: int | None
    first_missing_month: str | None
    sec_fact_rows: int | None
    sec_cik_mapped_us: int | None
    price_series: int | None
    adjusted_series: int | None
    reported_adjusted_bar_rows: int | None
    split_event_rows: int | None
    dividend_event_rows: int | None
    pilot_price_selections: int | None
    backtest_adjusted_selections: int | None
    wf5_run_rows: int | None
    wf6_run_rows: int | None
    wf8_activation_rows: int | None
    pit_daily_status: str
    pit_daily_date_utc: str | None
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    wf9_activated_by_this_panel: bool = False


def _monthly_ends(start: date, end: date) -> list[str]:
    cursor = date(start.year, start.month, 1)
    result = []
    while cursor <= end:
        last = date(cursor.year, cursor.month, monthrange(cursor.year, cursor.month)[1])
        if start <= last <= end:
            result.append(last.isoformat())
        cursor = date(cursor.year + (cursor.month == 12), 1 if cursor.month == 12 else cursor.month + 1, 1)
    return result


class DataControlCenterService:
    def __init__(self, root: Path | None = None, *, runtime_root: Path | None = None) -> None:
        if runtime_root is not None:
            self.runtime_root = Path(runtime_root)
        elif os.environ.get("S153_RUNTIME_ROOT"):
            self.runtime_root = Path(os.environ["S153_RUNTIME_ROOT"])
        elif getattr(sys, "frozen", False):
            self.runtime_root = runtime_state_dir() / "runtime"
        elif root is not None:
            self.runtime_root = Path(root)
        else:
            raise ValueError("A project root or actual runtime root is required")

    @property
    def db_path(self) -> Path:
        return self.runtime_root / "data" / "runtime" / "operational.db"

    def snapshot(self) -> ControlCenterSnapshot:
        now = datetime.now(timezone.utc)
        months = _monthly_ends(date(2013, 1, 1), date(2024, 12, 31))
        values: dict[str, object] = {}
        blockers: list[str] = []
        warnings = [
            "Membership counts are not independently PIT-certified.",
            "Price registry totals do not prove daily bar/adjustment/delisting completeness.",
            "SEC rows do not prove exact filing acceptance timestamps or S15 readiness.",
            "WF5/WF6/WF8 row counts are not proof of WF9 activation or model accuracy.",
        ]
        db = self.db_path
        if not db.is_file() or db.is_symlink():
            blockers.append("LOCAL_OPERATIONAL_DB_NOT_FOUND")
        else:
            # Connecting with URI mode=ro refuses missing files; query_only
            # forbids accidental SQL mutations even if refactored later.
            with closing(sqlite3.connect(db.resolve().as_uri() + "?mode=ro",
                                         uri=True, timeout=0.75)) as conn:
                conn.execute("PRAGMA query_only=ON")
                conn.execute("PRAGMA busy_timeout=750")
                names = {r[0] for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )}
                def scalar(table: str, query: str) -> int | None:
                    if table not in names:
                        blockers.append("MISSING_TABLE_" + table.upper())
                        return None
                    result = conn.execute(query).fetchone()
                    return int(result[0] or 0) if result is not None else 0

                if "universe_snapshot_membership" in names:
                    existing = {r[0] for r in conn.execute(
                        """SELECT DISTINCT snapshot_date FROM universe_snapshot_membership
                           WHERE snapshot_date BETWEEN '2013-01-01' AND '2024-12-31'
                             AND source IN ('ALPHAVANTAGE_PIT','MASSIVE_PIT')"""
                    )}
                    existing_months = existing.intersection(months)
                    missing = [month for month in months if month not in existing_months]
                    values.update(pit_present=len(existing_months),
                                  pit_missing=len(missing),
                                  first_missing_month=missing[0] if missing else None)
                    if missing:
                        blockers.append("HISTORICAL_MONTHLY_PIT_LISTINGS_INCOMPLETE")
                else:
                    blockers.append("MISSING_TABLE_UNIVERSE_SNAPSHOT_MEMBERSHIP")

                values["sec_fact_rows"] = scalar(
                    "fundamental_facts_source",
                    "SELECT COUNT(*) FROM fundamental_facts_source WHERE source='SEC_EDGAR'"
                )
                values["sec_cik_mapped_us"] = scalar(
                    "security_master",
                    """SELECT COUNT(*) FROM security_master WHERE market='US'
                        AND cik IS NOT NULL AND cik<>''"""
                )
                if "price_series_registry" in names:
                    row = conn.execute(
                        """SELECT COUNT(*),
                                  SUM(CASE WHEN adjustment_status IN
                                    ('DUAL_RAW_ADJUSTED','PROVIDER_ADJUSTED','ADJUSTED_ONLY')
                                    THEN 1 ELSE 0 END),
                                  SUM(CASE WHEN adjustment_status IN
                                    ('DUAL_RAW_ADJUSTED','PROVIDER_ADJUSTED','ADJUSTED_ONLY')
                                    THEN row_count ELSE 0 END)
                           FROM price_series_registry"""
                    ).fetchone()
                    values.update(price_series=int(row[0] or 0),
                                  adjusted_series=int(row[1] or 0),
                                  reported_adjusted_bar_rows=int(row[2] or 0))
                else:
                    blockers.append("MISSING_TABLE_PRICE_SERIES_REGISTRY")

                for field, table in (
                    ("split_event_rows","split_events_source"),
                    ("dividend_event_rows","dividend_events_source"),
                    ("wf5_run_rows","wf5_replay_runs"),
                    ("wf6_run_rows","wf6_walk_forward_runs"),
                    ("wf8_activation_rows","wf8_production_activations"),
                ):
                    values[field] = scalar(table, "SELECT COUNT(*) FROM " + table)
                for field, purpose in (
                    ("pilot_price_selections","PHASE14_ADJUSTED_PILOT_UNVERIFIED"),
                    ("backtest_adjusted_selections","BACKTEST_ADJUSTED"),
                ):
                    values[field] = scalar(
                        "canonical_price_selection",
                        "SELECT COUNT(*) FROM canonical_price_selection WHERE purpose='"
                        + purpose + "'"
                    )

        daily_file = self.runtime_root / "data/runtime/pit_daily_sync/latest_status.json"
        daily_status, daily_date = "NO_AUTOMATION_REPORT", None
        if daily_file.is_file() and not daily_file.is_symlink():
            try:
                raw = json.loads(daily_file.read_text(encoding="utf-8"))
                daily_status = str(raw.get("status") or "UNKNOWN")
                daily_date = str(raw.get("utc_date") or "") or None
            except (ValueError, OSError, TypeError):
                daily_status = "INVALID_AUTOMATION_REPORT"
        if values.get("backtest_adjusted_selections") == 0:
            blockers.append("NO_CANONICAL_BACKTEST_ADJUSTED_SELECTIONS")
        # Snapshot failures deliberately bubble to the dialog as errors, not
        # as invented zero counts; no busy-retry loop competing with SEC.
        return ControlCenterSnapshot(
            observed_at=now,
            source="LOCAL_M10_SQLITE_READ_ONLY",
            pit_present=values.get("pit_present"),
            pit_target=len(months),
            pit_missing=values.get("pit_missing"),
            first_missing_month=values.get("first_missing_month"),
            sec_fact_rows=values.get("sec_fact_rows"),
            sec_cik_mapped_us=values.get("sec_cik_mapped_us"),
            price_series=values.get("price_series"),
            adjusted_series=values.get("adjusted_series"),
            reported_adjusted_bar_rows=values.get("reported_adjusted_bar_rows"),
            split_event_rows=values.get("split_event_rows"),
            dividend_event_rows=values.get("dividend_event_rows"),
            pilot_price_selections=values.get("pilot_price_selections"),
            backtest_adjusted_selections=values.get("backtest_adjusted_selections"),
            wf5_run_rows=values.get("wf5_run_rows"),
            wf6_run_rows=values.get("wf6_run_rows"),
            wf8_activation_rows=values.get("wf8_activation_rows"),
            pit_daily_status=daily_status,
            pit_daily_date_utc=daily_date,
            blockers=tuple(dict.fromkeys(blockers)),
            warnings=tuple(warnings),
        )
