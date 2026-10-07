from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from app.bootstrap import AppContainer
from core.backtest.wf9_execution import WF9FullHistoricalExecution


def main() -> int:
    parser=argparse.ArgumentParser(
        description="Run WF9 full PIT historical evidence generation"
    )
    parser.add_argument("--start",default="2013-01-01")
    parser.add_argument("--end",default="2024-12-31")
    parser.add_argument("--first-test-year",type=int,default=2018)
    parser.add_argument("--last-test-year",type=int,default=2024)
    parser.add_argument("--code-identity",required=True)
    parser.add_argument("--preflight-only",action="store_true")
    args=parser.parse_args()

    root=Path(__file__).resolve().parents[1]
    app=AppContainer(root)
    app.initialize()
    try:
        runner=WF9FullHistoricalExecution(app)
        if args.preflight_only:
            report=runner.preflight(
                start_date=date.fromisoformat(args.start),
                end_date=date.fromisoformat(args.end),
            )
            print(json.dumps(asdict(report),indent=2,default=str))
            return 0 if report.ready else 2

        report=runner.run(
            start_date=date.fromisoformat(args.start),
            end_date=date.fromisoformat(args.end),
            first_test_year=args.first_test_year,
            last_test_year=args.last_test_year,
            code_identity=args.code_identity,
        )
        print(json.dumps(asdict(report),indent=2,default=str))
        return 0 if report.status=="COMPLETE_AND_ACTIVATED" else 2
    finally:
        app.close()


if __name__=="__main__":
    raise SystemExit(main())
