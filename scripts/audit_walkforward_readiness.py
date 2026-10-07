from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from app.bootstrap import AppContainer
from core.research.walkforward_readiness import WalkForwardReadinessAuditor


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit free/PIT walk-forward readiness")
    parser.add_argument("--date", action="append", dest="dates", help="YYYY-MM-DD; repeatable")
    parser.add_argument("--all-snapshots", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    app = AppContainer(root)
    app.initialize()
    try:
        auditor = WalkForwardReadinessAuditor(app.sqlite)
        if args.all_snapshots:
            dates = auditor.available_snapshot_dates()
        elif args.dates:
            dates = [date.fromisoformat(value) for value in args.dates]
        else:
            dates = auditor.available_snapshot_dates()[-12:]

        rows = auditor.audit_many(dates)
        print(json.dumps([
            {
                "as_of_date": row.as_of_date.isoformat(),
                "universe_members": row.universe_members,
                "exact_pit_universe": row.exact_pit_universe,
                "price_covered": row.price_covered,
                "price_coverage_pct": round(row.price_coverage_pct, 2),
                "fundamental_covered": row.fundamental_covered,
                "fundamental_coverage_pct": round(row.fundamental_coverage_pct, 2),
                "feature_covered": row.feature_covered,
                "feature_coverage_pct": round(row.feature_coverage_pct, 2),
                "v141_upstream_ready": row.v141_upstream_ready,
                "v141_upstream_ready_pct": round(row.v141_upstream_ready_pct, 2),
                "blockers": list(row.blockers),
            }
            for row in rows
        ], indent=2))
        return 0
    finally:
        app.close()


if __name__ == "__main__":
    raise SystemExit(main())
