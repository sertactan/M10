"""Replay V7 + V8 SEC evidence and build a sealed, research-only V8 staging report."""
from __future__ import annotations

import argparse
from pathlib import Path
import json
import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.scoring_completion import load_report, save_report
from app.scoring_v8_report import attach_v8_s9_audits, read_sealed_audit
from scripts.scoring_v8_s9_audit import run, store_or_verify


def main():
    runtime = Path(os.environ["LOCALAPPDATA"])/"S153ResearchTerminal"/"runtime"
    v8private = Path("E:/M10/.scoring_v8_private")
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--v7-report", type=Path,
        default=Path("E:/M10/.scoring_v7_private/scoring_completion/piotroski_s9/report.json"))
    p.add_argument("--s9-audit",type=Path,
        default=v8private/"piotroski_audit"/"source_pinned.json")
    p.add_argument("--phase27",type=Path,
        default=runtime/"phase27"/"current_scoring"/"staging.db")
    p.add_argument("--phase28",type=Path,
        default=runtime/"phase28"/"real_scoring_v1"/"stage.db")
    p.add_argument("--output",type=Path,
        default=v8private/"scoring_completion"/"v8_source_pinned_report.json")
    args=p.parse_args()
    if args.output.resolve().parent != (v8private/"scoring_completion").resolve():
        raise ValueError("V8_NEW_PRIVATE_REPORT_REQUIRED")
    # Original V7 loader cryptographically and independently replays all 15
    # accepted Research scores from sealed SEC source receipts.
    baseline=load_report(args.v7_report,args.phase27,args.phase28)
    audits = store_or_verify(args.s9_audit,
        runtime/"bulk"/"sec"/"companyfacts.zip",runtime,
        Path("E:/M10/.scoring_v6_private"),v8private)
    stored, digest = read_sealed_audit(args.s9_audit)
    if audits!=stored:
        raise ValueError("V8_S9_INDEPENDENT_OFFLINE_REPLAY_MISMATCH")
    report = attach_v8_s9_audits(baseline,stored,digest)
    save_report(report,args.output)
    verified = load_report(args.output,args.phase27,args.phase28)
    if verified != report or verified["full_model_count"] != 15:
        raise ValueError("V8_POST_WRITE_REPLAY_CHANGED")
    print(json.dumps({"status":"RESEARCH_ONLY_STAGING_SEALED",
                      "total_research_scores":15,"new_full_research_scores":0,
                      "canonical_pit_accepted":0,"s16_c_pit_features":0,
                      "INOD_S9":"N/A_8_OF_9_VERIFIED",
                      "CRMD_S9":"N/A_7_OF_9_VERIFIED",
                      "report":str(args.output),"s9_audit_sha256":digest},sort_keys=True))


if __name__=='__main__': main()
