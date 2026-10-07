from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from app.bootstrap import AppContainer
from core.backtest.wf6_walk_forward import WF6WalkForwardEngine


def main() -> int:
    parser=argparse.ArgumentParser(description="Run WF6 expanding walk-forward validation")
    parser.add_argument("--wf5-run-id", required=True)
    parser.add_argument("--reference-start-year", type=int, default=2013)
    parser.add_argument("--first-test-year", type=int, default=2018)
    parser.add_argument("--last-test-year", type=int, default=2024)
    parser.add_argument("--run-id", default=None)
    args=parser.parse_args()

    root=Path(__file__).resolve().parents[1]
    app=AppContainer(root)
    app.initialize()
    try:
        report=WF6WalkForwardEngine(app.sqlite).run(
            source_wf5_run_id=args.wf5_run_id,
            reference_start_year=args.reference_start_year,
            first_test_year=args.first_test_year,
            last_test_year=args.last_test_year,
            run_id=args.run_id,
        )
        print(json.dumps(asdict(report),indent=2,default=str))
        return 0 if report.status=="COMPLETE" else 2
    finally:
        app.close()


if __name__=="__main__":
    raise SystemExit(main())
