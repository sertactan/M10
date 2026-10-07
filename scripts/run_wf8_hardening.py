from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from app.bootstrap import AppContainer
from core.backtest.wf8_hardening import WF8ProductionHardeningAuditor


def main() -> int:
    parser=argparse.ArgumentParser(
        description="Run WF8 production hardening audit"
    )
    parser.add_argument("--wf7-run-id", required=True)
    args=parser.parse_args()

    root=Path(__file__).resolve().parents[1]
    app=AppContainer(root)
    app.initialize()
    try:
        report=WF8ProductionHardeningAuditor(app.sqlite).audit(
            wf7_run_id=args.wf7_run_id,
            persist=True,
        )
        print(json.dumps(asdict(report),indent=2,default=str))
        return 0 if report.status=="PRODUCTION_EVIDENCE_READY" else 2
    finally:
        app.close()


if __name__=="__main__":
    raise SystemExit(main())
