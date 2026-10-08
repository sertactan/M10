from __future__ import annotations

"""Read-only review of implausibly future-dated SEC financial periods.

Run on a local, verified SQLite BACKUP rather than the live import database.
An SEC Companyfacts file can contain periods beyond today's date: such rows
must not enter historic actuals. This audit never rewrites facts, never
guesses accepted_at, and does not certify SEC PIT or WF9.
"""

import argparse
from contextlib import closing
from datetime import date, datetime, timezone
import json
from pathlib import Path
import sqlite3

SCHEMA = "MERIDYEN_PHASE14_SEC_TEMPORAL_OUTLIER_AUDIT_V1"


def audit(db_path: Path, *, as_of: date, limit: int = 1000) -> dict:
    if not 1 <= limit <= 10_000:
        raise ValueError("limit must be between 1 and 10000")
    if db_path.is_symlink() or not db_path.is_file():
        raise ValueError("An existing regular SQLite backup is required")
    report = {
        "schema": SCHEMA,
        "database": str(db_path.resolve()),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "as_of": as_of.isoformat(),
        "mode": "SQLITE_READ_ONLY_NO_NETWORK_NO_REPAIR",
        "status": "BLOCKED",
        "rows_matching_sampled": 0,
        "result_truncated": False,
        "counts_in_bounded_sample": {},
        "examples": [],
        "raw_records_modified": False,
        "historical_pit_certified": False,
        "wf9_activated": False,
    }
    # Never initialize/migrate user DB. query_only guards against accidental writes.
    with closing(sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro",
                                 uri=True, timeout=1.0)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        cols = {r["name"] for r in conn.execute(
            "PRAGMA table_info(fundamental_facts_source)"
        )}
        needed = {"fact_id", "security_id", "source", "period_end",
                  "filing_date", "available_at", "accession_number"}
        if not needed.issubset(cols):
            report["status"] = "BLOCKED_SCHEMA_INCOMPLETE"
            return report
        # A limited audit of MATCHES (not total rows or random sampling).
        # Date columns are normalized ISO YYYY-MM-DD by repository writes.
        rows = conn.execute(
            """SELECT fact_id,security_id,period_end,filing_date,
                      available_at,accession_number
               FROM fundamental_facts_source
               WHERE source='SEC_EDGAR'
                 AND (period_end>? OR (
                     filing_date IS NOT NULL AND period_end>filing_date))
               ORDER BY rowid DESC LIMIT ?""",
            (as_of.isoformat(), limit + 1),
        ).fetchall()
        report["result_truncated"] = len(rows) > limit
        from collections import Counter
        counts = Counter()
        for row in rows[:limit]:
            period = row["period_end"]
            filing = row["filing_date"]
            if period and str(period) > as_of.isoformat():
                counts["PERIOD_END_AFTER_AUDIT_DATE"] += 1
            if period and filing and str(period) > str(filing):
                counts["PERIOD_END_AFTER_FILING_DATE"] += 1
            if len(report["examples"]) < 25:
                report["examples"].append({
                    key: row[key] for key in (
                        "fact_id", "security_id", "period_end",
                        "filing_date", "available_at", "accession_number"
                    )
                })
        report["rows_matching_sampled"] = min(len(rows), limit)
        report["counts_in_bounded_sample"] = dict(sorted(counts.items()))
        report["status"] = (
            "OUTLIERS_FOUND_REVIEW_REQUIRED" if rows else
            "NO_MATCHES_IN_THIS_QUERY_NOT_FULL_PIT_CERTIFICATION"
        )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--as-of", type=date.fromisoformat,
                        default=datetime.now(timezone.utc).date())
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        src = args.db.expanduser().resolve()
        out = args.out.expanduser().resolve()
        if src == out:
            raise ValueError("Report must not overwrite the source database")
        report = audit(args.db, as_of=args.as_of, limit=args.limit)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
        print(json.dumps({
            "status": report["status"],
            "sampled": report["rows_matching_sampled"],
            "truncated": report["result_truncated"],
            "report": str(out),
            "db_modified": False,
        }))
    except (sqlite3.Error, OSError, ValueError) as exc:
        parser.exit(2, "SEC_TEMPORAL_AUDIT_BLOCKED: " + type(exc).__name__ + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
