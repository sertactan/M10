from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from app.bootstrap import AppContainer
from core.backtest.wf8_activation import WF8ProductionActivationService


def main() -> int:
    parser=argparse.ArgumentParser(description="WF8-D rollback-safe production activation")
    sub=parser.add_subparsers(dest="command",required=True)

    activate=sub.add_parser("activate")
    activate.add_argument("--manifest-id",required=True)
    activate.add_argument("--model-version",default="S15.3_V1.4.1")
    activate.add_argument("--reason",default="validated production promotion")

    resolve=sub.add_parser("resolve")
    resolve.add_argument("--model-version",default="S15.3_V1.4.1")

    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    app=AppContainer(root)
    app.initialize()
    try:
        service=WF8ProductionActivationService(app.sqlite)
        if args.command=="activate":
            result=service.activate(
                manifest_id=args.manifest_id,
                model_version=args.model_version,
                reason=args.reason,
            )
        else:
            result=service.resolve_active(args.model_version)
        print(json.dumps(asdict(result),indent=2,default=str))
        return 0
    finally:
        app.close()


if __name__=="__main__":
    raise SystemExit(main())
