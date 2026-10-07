from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from app.bootstrap import AppContainer
from core.backtest.wf5_replay import WF5WholeMarketReplay


def main() -> int:
    parser=argparse.ArgumentParser(
        description="Run/resume WF5 PIT whole-market replay"
    )
    parser.add_argument("--start", default="2013-01-01")
    parser.add_argument("--end", default="2024-12-31")
    parser.add_argument("--run-id", default=None)
    args=parser.parse_args()

    start=date.fromisoformat(args.start)
    end=date.fromisoformat(args.end)
    if end < start:
        parser.error("--end must be >= --start")

    root=Path(__file__).resolve().parents[1]
    app=AppContainer(root)
    app.initialize()
    try:
        report=WF5WholeMarketReplay(app).run_range(
            start_date=start,
            end_date=end,
            run_id=args.run_id,
        )
        print(json.dumps(asdict(report),indent=2,default=str))
        return 0 if report.status=="COMPLETE" else 2
    finally:
        app.close()


if __name__=="__main__":
    raise SystemExit(main())
