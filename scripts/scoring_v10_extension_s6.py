"""Offline source replay for ETON S6 candidate, gated against score promotion."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.scoring_v10_extension_s6 import candidate_from_pinned_sec, CIK

PRIVATE = Path("E:/M10/.scoring_v10_private/extension_s6")


def run(output: Path, verify: bool) -> dict:
    archive = Path(os.environ["LOCALAPPDATA"])/"S153ResearchTerminal/runtime/bulk/sec/companyfacts.zip"
    with zipfile.ZipFile(archive) as z:
        data = candidate_from_pinned_sec(z.read(f"CIK{CIK}.json"))
    raw = (json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+"\n").encode()
    digest = sha256(raw).hexdigest()
    seal = Path(str(output)+".sha256")
    if output.resolve().parent != PRIVATE.resolve() or output.is_symlink() or seal.is_symlink():
        raise ValueError("S6_PRIVATE_V10_ROOT_REQUIRED")
    if verify:
        if output.read_bytes()!=raw or seal.read_text("ascii").strip()!=digest:
            raise ValueError("ETON_ORIGINAL_SEC_REPLAY_OR_SEAL_FAILED")
    else:
        output.parent.mkdir(parents=True,exist_ok=True)
        with output.open("xb") as f:f.write(raw)
        with seal.open("x",encoding="ascii") as f:f.write(digest+"\n")
    return {"status":"RESEARCH_CANDIDATE_ONLY_NOT_S6_FULL_SCORE",
            "ticker":"ETON","conditional_frozen_F":data["F_D_conditional"],
            "conditional_bin":data["candidate_bin"],"accepted_S6":data["S6_score"],
            "source_sha256":data["source_hash"],"private_receipt_sha256":digest,
            "offline_replay":verify}


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify",action="store_true")
    parser.add_argument("--output",type=Path,default=PRIVATE/"eton_s6_candidate_v1.json")
    args=parser.parse_args()
    print(json.dumps(run(args.output,args.verify),sort_keys=True))
