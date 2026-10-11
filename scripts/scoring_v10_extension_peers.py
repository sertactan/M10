"""Offline V10 extension of frozen S10 (FY2020-24) and TMDX/PENG S11.

python -B scripts/scoring_v10_extension_peers.py
python -B scripts/scoring_v10_extension_peers.py --verify-only
Output is SHA-sealed PRIVATE evidence; never written into tracked repository.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.scoring_v10_extension_peers import audit_extension


PRIVATE = Path("E:/M10/.scoring_v10_private/extension_peers")
RECEIPT = PRIVATE / "source_replay.json"


def calculate():
    runtime = Path(os.environ["LOCALAPPDATA"])/"S153ResearchTerminal"/"runtime"
    return audit_extension(
        runtime=runtime, legacy_root=Path("E:/M10/.scoring_v6_private"),
        task9_cache=runtime/"scoring_completion"/"task9_jones",
        s10_cache=Path("E:/M10/.scoring_v10_private/s10/task9_jones_v10_s10"),
    )


def run(*, verify_only=False, receipt=RECEIPT):
    receipt=Path(receipt)
    if receipt.resolve().parent != PRIVATE.resolve() or receipt.is_symlink():
        raise ValueError("EXTENSION_PRIVATE_PATH_REQUIRED")
    data=calculate()  # Independent full original-byte replay on every call.
    if data["new_verified_full_research_scores"] or data["new_canonical_PIT_scores"]:
        raise ValueError("EXTENSION_UNSUPPORTED_SCORE_PROMOTION")
    raw=(json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False,
                    allow_nan=False)+"\n").encode("utf8")
    digest=sha256(raw).hexdigest()
    seal=Path(str(receipt)+".sha256")
    if receipt.is_file():
        if (not seal.is_file() or seal.is_symlink()
                or receipt.read_bytes()!=raw
                or seal.read_text("ascii").strip()!=digest):
            raise ValueError("EXTENSION_ORIGINAL_SOURCE_REPLAY_OR_SHA_SEAL_CHANGED")
    elif verify_only:
        raise ValueError("EXTENSION_PRIVATE_RECEIPT_REQUIRED")
    else:
        if seal.exists():
            raise ValueError("EXTENSION_RECEIPT_SHA_COLLISION")
        receipt.parent.mkdir(parents=True,exist_ok=True)
        with receipt.open("xb") as stream:
            stream.write(raw)
        with seal.open("x",encoding="ascii") as stream:
            stream.write(digest+"\n")
    return data,digest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    args=parser.parse_args()
    result,digest=run(verify_only=args.verify_only)
    summary={
        "S10_full_FY2020_FY2024": result["S10"]["full_new_S10_scores"],
        "S10_independent_source_design_years":{
            k:v["source_bounded_real_TCA_design_years"]
            for k,v in result["S10"]["stocks"].items()},
        "S10_original_historical_SIC_headers_per_year":
            result["S10"]["cached_historical_original_10k_SIC_headers_per_year"],
        "S11":{k:{"score":v["full_research_score"],
                   "sic":v["sic"],"peer_count":v["source_verified_independent_peers"],
                   "minimum":v["required_independent_peers"],
                   "accession":v["accession"],"header_sha256":v["original_sgml_header_sha256"],
                   "offline_replay":v["offline_SEC_original_bytes_replayed"]}
               for k,v in result["S11"].items()},
        "new_complete_research_scores":result["new_verified_full_research_scores"],
        "network_requests":result["network_requests"],
        "receipt":str(RECEIPT),"receipt_sha256":digest,
    }
    print(json.dumps(summary,indent=2,sort_keys=True,ensure_ascii=False))


if __name__ == "__main__":
    main()
