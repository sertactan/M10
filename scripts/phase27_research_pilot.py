"""On-demand current research pilot; no automatic access to live M10 database."""
from __future__ import annotations

import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.phase27_current_scoring import check_ticker, run_pilot


def main() -> int:
    parser = argparse.ArgumentParser(description="M10 Phase27 offline/online research-only stage")
    parser.add_argument("--stage-db", type=Path, required=True,
                        help="Must be an isolated phase27/staging SQLite file")
    parser.add_argument("--archive", type=Path,
                        help="Explicit verified historical archive for read-only SEC cached facts")
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--offline", action="store_true", help="Never make a network request")
    args = parser.parse_args()
    ticker = check_ticker(args.ticker)
    if args.offline:
        if args.stage_db.is_symlink() or not args.stage_db.is_file():
            print("MISSING_DATA: stage does not exist")
            return 2
        with closing(sqlite3.connect(args.stage_db.resolve().as_uri() + "?mode=ro", uri=True)) as db:
            row = db.execute("SELECT details_json FROM stock_runs WHERE ticker=?", (ticker,)).fetchone()
        if row is None:
            print(f"MISSING_DATA: no report for {ticker}")
            return 2
        report = json.loads(row[0])
    else:
        if args.archive is None:
            parser.error("--archive is required for an online research pilot")
        report = run_pilot(args.stage_db, args.archive, ticker)
    print(json.dumps({
        "ticker": report["ticker"],
        "price": report["price"],
        "currency": report["currency"],
        "quote_time": report["quote_time"],
        "quote_status": report["quote_status"],
        "financial_period": report["financial_period"],
        "financial_status": report["financial_status"],
        "bars": report["bars"],
        "research_feature_count": report["raw_research_features"],
        "research_features": report["research_features"],
        "models": [
            {"model": item["model"],"score":item["score"],"status":item["status"],
             "coverage":item["coverage"],"missing":item["missing"]}
            for item in report["model_audits"]
        ],
        "canonical_accepted": [0, 0],
        "WF9": "BLOCKED",
        "LearningV3": "NOT_TRAINED",
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
