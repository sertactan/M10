"""Standalone offline Phase28 INOD pilot; does not query providers or live DB."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import json
import sqlite3
from contextlib import closing

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.phase28_real_scoring import run_phase28


def main() -> int:
    p=argparse.ArgumentParser(description="Phase28 offline current research feature completion")
    p.add_argument("--phase27-db", type=Path, required=True)
    p.add_argument("--phase28-db", type=Path, required=True)
    p.add_argument("--archive", type=Path, help="Existing read-only SEC origin archive")
    p.add_argument("--ticker",default="INOD")
    p.add_argument("--inspect-only",action="store_true",help="Never write a database")
    args=p.parse_args()
    if args.ticker!="INOD":
        p.error("Only INOD permitted until first independently evidenced full-score acceptance")
    if args.inspect_only:
        if not args.phase28_db.is_file() or args.phase28_db.is_symlink():
            print("MISSING_DATA: Phase28 stage not found",file=sys.stderr)
            return 2
        with closing(sqlite3.connect(args.phase28_db.resolve().as_uri()+"?mode=ro",uri=True)) as db:
            row=db.execute("SELECT report_json FROM phase28_runs WHERE ticker='INOD'").fetchone()
        if row is None:
            print("MISSING_DATA: No INOD Phase28 report",file=sys.stderr)
            return 2
        report=json.loads(row[0])
    else:
        if args.archive is None:
            p.error("--archive required for offline source read")
        report=run_phase28(args.phase27_db,args.phase28_db,args.archive)
    print(json.dumps({
        "ticker":report["ticker"],
        "price":report["price"],"price_time":report["price_time"],
        "financial_period":report["financial_period"],"currency":report["currency"],
        "research_feature_count":report["phase28_feature_count"],
        "full_model_score_count":report["full_model_score_count"],
        "model_matrix":[{"model":x["model"],"score":x["score"],
                         "status":x["status"],"present":x["present"],
                         "required":x["required"],"missing":x["missing"]}
                        for x in report["models"]],
        "partial_components":report["diagnostics"],
        "historical_canonical": [0,0],"WF9":"BLOCKED",
        "LearningV3":"NOT_TRAINED"
    },indent=2,ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
