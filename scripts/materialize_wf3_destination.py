from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from app.bootstrap import AppContainer
from core.features.wf3_bulk import WF3WholeUniverseMaterializer


def main() -> int:
    parser=argparse.ArgumentParser(description="Materialize WF3 destination engine for one PIT universe date")
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    args=parser.parse_args()

    root=Path(__file__).resolve().parents[1]
    app=AppContainer(root)
    app.initialize()
    try:
        report=WF3WholeUniverseMaterializer(app).materialize_date(date.fromisoformat(args.date))
        payload=asdict(report)
        payload["as_of_date"]=report.as_of_date.isoformat()
        print(json.dumps(payload,indent=2))
        return 0
    finally:
        app.close()


if __name__ == "__main__":
    raise SystemExit(main())
