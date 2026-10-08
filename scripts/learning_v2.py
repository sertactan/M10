from __future__ import annotations

"""M10 Learning Engine V2: evidence journal, audit and consistent backup.

Run from repository root. No API keys required. No continuous remote agent.
"""
import argparse
import json
from pathlib import Path
from core.learning_v2.journal import connect, learn_backtest, record_feedback, audit, backup
from scripts.import_research_pilot import import_pilot, audit_research


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db",type=Path,default=Path("data/runtime/meridyen_learning.sqlite3"))
    sub=ap.add_subparsers(dest="command",required=True)
    sub.add_parser("init")
    learn=sub.add_parser("learn")
    learn.add_argument("--backtest",type=Path,required=True)
    learn.add_argument("--as-of",required=True)
    fb=sub.add_parser("feedback")
    fb.add_argument("--category",required=True)
    fb.add_argument("--note",required=True)
    fb.add_argument("--evidence-ref",required=True)
    improve=sub.add_parser("improve")
    improve.add_argument("--phase13-manifest",type=Path)
    back=sub.add_parser("backup")
    back.add_argument("--out-dir",type=Path,default=Path("data/runtime/learning_backups"))
    research=sub.add_parser("research-import", help="Archive source-checked SEC research evidence, not price outcomes")
    research.add_argument("--bundle", type=Path, required=True)
    sub.add_parser("research-audit", help="Read research-only evidence counts")
    args=ap.parse_args()
    try:
        if args.command=="init":
            conn=connect(args.db)
            conn.close()
            result={"status":"INITIALIZED","db":str(args.db)}
        elif args.command=="learn":
            result=learn_backtest(args.db,args.backtest,args.as_of)
        elif args.command=="feedback":
            result=record_feedback(args.db,args.category,args.note,args.evidence_ref)
        elif args.command=="improve":
            result=audit(args.db,args.phase13_manifest)
        elif args.command=="research-import":
            result=import_pilot(args.db,args.bundle)
        elif args.command=="research-audit":
            result=audit_research(args.db)
        else:
            result=backup(args.db,args.out_dir)
        print(json.dumps(result,indent=2,ensure_ascii=False))
    except (OSError,ValueError,KeyError,TypeError, json.JSONDecodeError) as exc:
        ap.exit(2,f"LEARNING_V2_BLOCKED: {exc}\n")


if __name__=="__main__":
    main()
