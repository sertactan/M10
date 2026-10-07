from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.bootstrap import AppContainer
from core.backtest.wf7_validation import WF7ValidationCalibrationEngine


def main() -> int:
    parser=argparse.ArgumentParser(
        description="Run WF7 OOS validation and empirical magnitude calibration"
    )
    parser.add_argument("--wf6-run-id", required=True)
    parser.add_argument("--run-id", default=None)
    args=parser.parse_args()

    root=Path(__file__).resolve().parents[1]
    app=AppContainer(root)
    app.initialize()
    try:
        engine=WF7ValidationCalibrationEngine(app.sqlite)
        run_id=engine.run(wf6_run_id=args.wf6_run_id,run_id=args.run_id)
        summary=app.sqlite.connection.execute(
            "SELECT * FROM wf7_validation_summary WHERE run_id=?",
            (run_id,),
        ).fetchone()
        thresholds=app.sqlite.connection.execute(
            "SELECT * FROM wf7_threshold_metrics WHERE run_id=? ORDER BY selector",
            (run_id,),
        ).fetchall()
        buckets=app.sqlite.connection.execute(
            "SELECT * FROM wf7_calibration_buckets WHERE run_id=? ORDER BY score_low",
            (run_id,),
        ).fetchall()
        print(json.dumps({
            "run_id":run_id,
            "summary":dict(summary) if summary else None,
            "thresholds":[dict(row) for row in thresholds],
            "calibration_buckets":[dict(row) for row in buckets],
        },indent=2,default=str))
        return 0
    finally:
        app.close()


if __name__=="__main__":
    raise SystemExit(main())
