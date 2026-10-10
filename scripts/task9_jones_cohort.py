"""Reproducible V4 Task9 SEC FY2025 SIC7374 peer scan, private output only.

Default invocation:
  python scripts/task9_jones_cohort.py --pages 12 --budget 100 --max-candidates 75

Never writes in repo/DB/EXE, never retries HTTP 403 or 429. Any response bytes,
filing header excerpts, source receipts and detailed exclusions are stored in
%LOCALAPPDATA%/S153ResearchTerminal/runtime/scoring_completion/task9_jones/.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from app.task9_jones_cohort import SECCache, read_sec_contact, scan_task9


def private_root():
    return (Path(os.environ["LOCALAPPDATA"])/"S153ResearchTerminal"/"runtime"/
            "scoring_completion"/"task9_jones")


def save_report(report, root, *, stamp):
    root=Path(root).resolve()
    expected=private_root().resolve()
    if root!=expected:
        raise ValueError("Task9 report must stay in PRIVATE task9_jones runtime cache")
    out=root/"reports"/("task9_jones_"+stamp+".json")
    out.parent.mkdir(exist_ok=True,parents=True)
    raw=json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False).encode()
    with out.open("xb") as f:
        f.write(raw)
    sha=sha256(raw).hexdigest()
    with Path(str(out)+".sha256").open("x",encoding="ascii") as f:
        f.write(sha+"\n")
    return out,sha


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pages",type=int,default=12)
    p.add_argument("--budget",type=int,default=100)
    p.add_argument("--max-candidates",type=int,default=75)
    p.add_argument("--dry-cache-only",action="store_true")
    args=p.parse_args(argv)
    if not (1<=args.pages<=30 and 0<=args.budget<=300
            and 0<=args.max_candidates<=300):
        p.error("Invalid bounded page/request/candidate arguments")
    cache=private_root()
    runtime=cache.parents[1]
    conf=Path("E:/M10/.env")
    contact=None if args.dry_cache_only else read_sec_contact(conf)
    session=SECCache(cache,contact=contact,request_budget=args.budget)
    started=datetime.now(timezone.utc)
    report=scan_task9(session,runtime=runtime,max_pages=args.pages,
                     max_candidates=args.max_candidates)
    stamp=started.strftime("%Y%m%dT%H%M%S%fZ")
    out,digest=save_report(report,cache,stamp=stamp)
    print(json.dumps({
        "private_report":str(out),
        "report_sha256":digest,
        "target_historical_SIC":(report.get("target") or {}).get("historical_sic"),
        "target_companyfacts_sha256":report["target_financial_companyfacts_sha256"],
        "official_sic_directory_candidates":report["sic_directory_candidates"],
        "zip_exact_field_8_of_8":report["precheck_8_of_8"],
        "dated_sic_7374_valid_peer_count":report["verified_same_sic_independent_peers"],
        "required_peer_count":report["required_peers"],
        "S11":report["s11_score"],
        "S11_blockers":report["s11_missing"],
        "stop_reason":report["stop_reason"],
        "network_requests":report["network_requests"],
        "http_statuses":report["http_statuses"],
    },ensure_ascii=False,indent=2))
    return report


if __name__=="__main__":
    main()
