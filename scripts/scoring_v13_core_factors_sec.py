"""Seal private original-source F52/F53 raw growth receipt."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.scoring_v13_core_factors_sec import calculate_raw_factors


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--companyfacts", required=True, type=Path)
    p.add_argument("--submissions", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args()
    result = calculate_raw_factors(args.companyfacts, args.submissions)
    raw = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(raw)
    args.out.with_name(args.out.name + ".sha256").write_text(sha256(raw).hexdigest()+"\n", encoding="ascii")
    print("INOD: F52/F53 original raw growth computed; normalized scores=N/A; S1-S3 complete=0")


if __name__ == "__main__":
    main()
