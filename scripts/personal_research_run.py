"""CLI: python scripts/personal_research_run.py --ticker INOD --root E:/M10"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.personal_research.evidence_store import EvidenceStore
from app.personal_research.pipeline import analyze, TARGETS
from app.personal_research.report_builder import export_report


def main(argv=None):
    parser = argparse.ArgumentParser(description="MERİDYEN Personal AI Research — offline")
    parser.add_argument("--ticker", choices=TARGETS, required=True)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--packet", help="Explicit offline evidence JSON packet")
    parser.add_argument("--period-end", help="Fiscal year end YYYY-MM-DD")
    parser.add_argument("--sidecar", help="Isolated SQLite path")
    parser.add_argument("--output", help="JSON/CSV output prefix")
    args = parser.parse_args(argv)
    root = Path(args.root)
    result = analyze(args.ticker, evidence_root=root, packet_path=args.packet,
                     fiscal_period=args.period_end)
    db = Path(args.sidecar) if args.sidecar else root / ".personal_research_ai_v1_private/runs.sqlite3"
    EvidenceStore(db).save(result)
    prefix = Path(args.output) if args.output else root / ".personal_research_ai_v1_private/exports" / (
        args.ticker.lower() + "_latest")
    json_path, csv_path = export_report(result, prefix)
    print(json.dumps({
        "ticker": result["ticker"], "period_end": result["period_end"],
        "baseline": result["baseline"], "personal_models": {
            k: {"score": v.get("score"), "status": v.get("status"),
                "missing": v.get("missing")} for k, v in result["models"].items()},
        "run_receipt_sha256": result["receipt_sha256"],
        "json": str(json_path), "csv": str(csv_path), "sidecar": str(db),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
