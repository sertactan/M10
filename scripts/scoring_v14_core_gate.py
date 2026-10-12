"""Build or byte-verify a private S1-S3 original-source gate receipt."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.scoring_v14_core_gate import build_gate_receipt


def main() -> None:
    p = argparse.ArgumentParser()
    for name in ("contract", "v12-report", "v13-raw-factors", "offline-db", "out"):
        p.add_argument("--"+name, type=Path, required=True)
    p.add_argument("--v13-sec-binding", type=Path)
    p.add_argument("--verify", action="store_true")
    args = p.parse_args()
    result = build_gate_receipt(contract=args.contract, v12_report=args.v12_report,
                                v13_raw_factors=args.v13_raw_factors, offline_db=args.offline_db,
                                v13_sec_binding=args.v13_sec_binding)
    raw = (json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    seal = args.out.with_name(args.out.name + ".sha256")
    digest = sha256(raw).hexdigest()
    if args.verify:
        if args.out.read_bytes() != raw or seal.read_text(encoding="ascii").strip() != digest:
            raise ValueError("private V14 core receipt or seal changed")
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        if args.out.exists() or seal.exists():
            raise ValueError("refusing to overwrite existing private receipt")
        args.out.write_bytes(raw)
        seal.write_text(digest + "\n", encoding="ascii")
    print(f"stocks={len(result['stocks'])} historical={result['offline_storage']['historical_observations']} new_scores=0 sha256={digest}")


if __name__ == "__main__":
    main()
