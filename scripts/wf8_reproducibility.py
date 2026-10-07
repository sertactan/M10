from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from app.bootstrap import AppContainer
from core.backtest.wf8_reproducibility import WF8ReproducibilityManifestService


def main() -> int:
    parser=argparse.ArgumentParser(description="Create or verify WF8 reproducibility manifest")
    sub=parser.add_subparsers(dest="command",required=True)

    create=sub.add_parser("create")
    create.add_argument("--hardening-id",required=True)
    create.add_argument("--code-identity",required=True)

    verify=sub.add_parser("verify")
    verify.add_argument("--manifest-id",required=True)

    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    app=AppContainer(root)
    app.initialize()
    try:
        service=WF8ReproducibilityManifestService(app.sqlite)
        if args.command=="create":
            manifest=service.create(
                hardening_id=args.hardening_id,
                code_identity=args.code_identity,
            )
        else:
            manifest=service.verify(args.manifest_id)
        print(json.dumps(asdict(manifest),indent=2,default=str))
        return 0
    finally:
        app.close()


if __name__=="__main__":
    raise SystemExit(main())
