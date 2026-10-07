from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from app.bootstrap import AppContainer
from core.backtest.production_evidence_chain import ProductionEvidenceChain


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the full Meridyen WF5->WF8 production evidence chain"
    )
    parser.add_argument("--start", default="2013-01-01")
    parser.add_argument("--end", default="2024-12-31")
    parser.add_argument("--reference-start-year", type=int, default=2013)
    parser.add_argument("--first-test-year", type=int, default=2018)
    parser.add_argument("--last-test-year", type=int, default=2024)
    parser.add_argument("--code-identity", required=True)
    parser.add_argument("--activate", action="store_true")
    parser.add_argument("--output", default="production_evidence_report.json")
    args = parser.parse_args()

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    if end < start:
        parser.error("--end must be >= --start")

    root = Path(__file__).resolve().parents[1]
    app = AppContainer(root)
    app.initialize()
    try:
        report = ProductionEvidenceChain(app).run(
            start_date=start,
            end_date=end,
            code_identity=args.code_identity,
            reference_start_year=args.reference_start_year,
            first_test_year=args.first_test_year,
            last_test_year=args.last_test_year,
            activate=args.activate,
        )
        payload = asdict(report)
        text = json.dumps(payload, indent=2, default=str)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
        print(text)
        return 0 if report.status in {
            "PRODUCTION_EVIDENCE_READY",
            "PRODUCTION_ACTIVE",
        } else 2
    finally:
        app.close()


if __name__ == "__main__":
    raise SystemExit(main())
