from __future__ import annotations

"""Phase 13: read-only production PIT readiness audit.

Run against the actual M10 Windows runtime database. Never bootstraps, scores,
changes model formulas, downloads prices, or activates production.
Empty GitHub Actions runners produce an honest BLOCKED_DB_NOT_FOUND report.
"""
import argparse
from dataclasses import asdict
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import sqlite3


SCHEMA = "MERIDYEN_PHASE13_READINESS_V1"
REQUIRED_TABLES = (
    "universe_snapshot_membership",
    "canonical_price_selection",
    "fundamental_facts_source",
    "canonical_model_features",
    "wf5_replay_runs",
)
DEFAULT_START = date(2013, 1, 1)
DEFAULT_END = date(2024, 12, 31)


def _iso(value, field):
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid {field}, expected YYYY-MM-DD: {value}")


def _month_ends(start, end):
    from calendar import monthrange
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        d = date(year, month, monthrange(year, month)[1])
        # Match M10's actual monthly snapshot anchor logic (the native
        # runner determines the final expected list).
        if start <= d <= end:
            yield d
        if month == 12:
            year, month = year + 1, 1
        else:
            month += 1


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def default_db_path(root=None):
    base = Path(os.getenv("S153_RUNTIME_ROOT") or root or Path(__file__).resolve().parents[1])
    return base / "data" / "runtime" / "operational.db"


def _check_tables(connection):
    existing = {
        str(row[0]) for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    return [name for name in REQUIRED_TABLES if name not in existing]


def evaluate(db_path, start=DEFAULT_START, end=DEFAULT_END):
    start, end = _iso(start, "start"), _iso(end, "end")
    if end < start:
        raise ValueError("end must not be before start")
    db = Path(db_path)
    data = {
        "schema": SCHEMA,
        "generated_at": _utc_now(),
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "execution_mode": "READ_ONLY_LOCAL_PIT_DIAGNOSTIC",
        "source_class": "LOCAL_M10_DB" if db.is_file() else "NO_LOCAL_M10_DB",
        "wf9_status": "NOT_EXECUTED",
        "wf9_activated": False,
        "pit_independently_verified": False,
        "blockers": [],
        "coverage": None,
        "sample_dates": [],
        "required_actions": [],
    }
    if not db.is_file():
        data["status"] = "BLOCKED_DB_NOT_FOUND"
        data["blockers"] = ["NO_LOCAL_M10_OPERATIONAL_DB"]
        data["required_actions"] = [
            "Run on the Windows machine hosting M10's actual operational.db.",
            "Provide --db pointing to M10 writable runtime data/runtime/operational.db.",
            "Do not infer Windows data availability from an empty GitHub Actions runner.",
        ]
        return data

    try:
        # URI ro ensures the diagnostic cannot create a new empty database.
        conn = sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            integrity = conn.execute("PRAGMA quick_check").fetchone()
            if integrity is None or str(integrity[0]).lower() != "ok":
                raise ValueError("SQLite quick_check failed")
            absent = _check_tables(conn)
            if absent:
                data["status"] = "BLOCKED_SCHEMA"
                data["blockers"] = ["MISSING_REQUIRED_TABLES"]
                data["missing_tables"] = absent
                data["required_actions"] = [
                    "Open the same M10 build once to run its validated schema migrations.",
                    "Verify this is M10 operational.db and not an empty journal or backup.",
                ]
                return data

            from types import SimpleNamespace
            from core.research.walkforward_readiness import WalkForwardReadinessAuditor
            from core.backtest.wf9_execution import WF9FullHistoricalExecution
            from core.backtest.wf5_schedule import monthly_snapshot_dates

            runner = object.__new__(WF9FullHistoricalExecution)
            runner.readiness = WalkForwardReadinessAuditor(SimpleNamespace(connection=conn))
            native_report = runner.preflight(start_date=start, end_date=end)
            expected = monthly_snapshot_dates(start, end)
            existing = set(runner.readiness.available_snapshot_dates())
            missing = [d.isoformat() for d in expected if d not in existing]
            counts = {
                "requested_monthly_dates": native_report.requested_snapshot_dates,
                "available_monthly_dates": native_report.existing_snapshot_dates,
                "exact_pit_dates": native_report.exact_pit_dates,
                "dates_with_adjusted_prices": native_report.any_adjusted_price_dates,
                "eligible_security_months": native_report.total_universe_observations,
                "adjusted_price_covered_security_months": native_report.total_price_covered,
                "missing_monthly_dates": missing,
            }
            data["coverage"] = counts
            data["blockers"] = list(native_report.blockers)
            data["warnings"] = list(native_report.warnings)

            # Sample only a few dates to keep this script manageable on very
            # large datasets; the native preflight checks the entire window.
            chosen = [d for d in expected if d in existing][:3]
            tail = [d for d in expected if d in existing][-3:]
            for d in dict.fromkeys(chosen + tail):
                point = runner.readiness.audit(d)
                data["sample_dates"].append({
                    "date": d.isoformat(),
                    "members": point.universe_members,
                    "exact_pit": point.exact_pit_universe,
                    "adjusted_price_covered": point.price_covered,
                    "fundamentals_covered": point.fundamental_covered,
                    "features_covered": point.feature_covered,
                    "v141_upstream_ready": point.v141_upstream_ready,
                    "blockers": list(point.blockers),
                })
            data["status"] = "PREFLIGHT_READY_NOT_ACTIVATED" if native_report.ready else "PREFLIGHT_BLOCKED"
            if not native_report.ready:
                if native_report.existing_snapshot_dates < native_report.requested_snapshot_dates:
                    data["required_actions"].append(
                        "Bootstrap all missing monthly exact-PIT universe snapshots; keep historical delistings."
                    )
                if native_report.any_adjusted_price_dates < native_report.requested_snapshot_dates or (
                    native_report.total_price_covered < native_report.total_universe_observations
                ):
                    data["required_actions"].append(
                        "Populate single-source canonical adjusted daily price coverage, including delistings."
                    )
                if any("FUNDAMENTAL" in x or "FEATURE" in x or "V141" in x for x in data["blockers"]):
                    data["required_actions"].append(
                        "Materialize dated SEC fundamental facts and S15.3 V1.4.1 PIT features; re-audit."
                    )
            else:
                data["required_actions"].append(
                    "Run scripts/run_wf9_full_execution.py with an audited code identity; verify COMPLETE_AND_ACTIVATED."
                )
        finally:
            conn.close()
    except (sqlite3.DatabaseError, OSError, ValueError, ImportError, ModuleNotFoundError) as exc:
        data["status"] = "BLOCKED_DIAGNOSTIC_ERROR"
        data["blockers"] = ["LOCAL_DB_OR_DEPENDENCY_AUDIT_FAILED"]
        data["error_class"] = type(exc).__name__
        data["required_actions"] = [
            "Check the M10 database schema, installed Python dependencies and runtime read permissions.",
            "Run full M10 python -m pytest and inspect local logs; do not report production success.",
        ]
    return data


def markdown_report(report):
    cov = report.get("coverage")
    lines = [
        "# Meridyen M10 — Phase 13 Real-Data Readiness",
        "",
        f"- Status: **{report['status']}**",
        f"- Window: {report['window']['start']} — {report['window']['end']}",
        f"- Source: {report['source_class']}",
        "- Execution: **READ ONLY**, no downloads and no production activation",
        "- Neither a PIT certificate nor an achieved investment backtest",
        "",
    ]
    if cov:
        lines += [
            "## Historical completeness",
            "",
            f"- Monthly snapshots: {cov['available_monthly_dates']} / {cov['requested_monthly_dates']}",
            f"- Exact PIT dates: {cov['exact_pit_dates']}",
            f"- Dates with adjusted prices: {cov['dates_with_adjusted_prices']}",
            f"- Covered security-months: {cov['adjusted_price_covered_security_months']} / {cov['eligible_security_months']}",
            f"- Missing monthly dates: {', '.join(cov['missing_monthly_dates'][:24]) or 'none'}" +
            (f" ... and {len(cov['missing_monthly_dates'])-24} more" if len(cov['missing_monthly_dates'])>24 else ""),
            "",
        ]
    lines += ["## Blockers", ""]
    lines += [f"- {b}" for b in report.get("blockers", [])] or ["- None on this preflight; activation still required"]
    lines += ["", "## Required next steps", ""]
    lines += [f"- {a}" for a in report.get("required_actions", [])] or ["- None"]
    lines += ["", "## Data privacy", "", "Only aggregate counts, status and blockers are included. Do not upload source SQLite/Parquet/portfolio data to a public repository.", ""]
    return "\n".join(lines)


def write_report(report, out_dir):
    output = Path(out_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "PHASE13_READINESS.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8"
    )
    (output / "PHASE13_READINESS.md").write_text(
        markdown_report(report), encoding="utf-8"
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=default_db_path())
    ap.add_argument("--start", default=DEFAULT_START.isoformat())
    ap.add_argument("--end", default=DEFAULT_END.isoformat())
    ap.add_argument("--out-dir", type=Path, default=Path("data/runtime/phase13_readiness"))
    ap.add_argument("--report-only", action="store_true",
                    help="Exit zero even when blocked, for CI diagnostic artifacts only")
    args = ap.parse_args()
    try:
        result = evaluate(args.db, args.start, args.end)
        write_report(result, args.out_dir)
        print(json.dumps({
            "status": result["status"],
            "blockers": result.get("blockers", []),
            "outputs": [str(args.out_dir / "PHASE13_READINESS.json"),
                        str(args.out_dir / "PHASE13_READINESS.md")],
        }, ensure_ascii=False))
        if result["status"] == "PREFLIGHT_READY_NOT_ACTIVATED":
            return 0
        return 0 if args.report_only else 2
    except (OSError, ValueError) as exc:
        ap.exit(2, f"PHASE13_REPORT_BLOCKED: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
