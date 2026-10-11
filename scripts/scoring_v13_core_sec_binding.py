"""Write a private read-only SEC timing receipt for existing core research legs."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.scoring_v13_core_sec_binding import bind_sec_acceptance


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--report", required=True, type=Path)
    p.add_argument("--submissions", required=True, type=Path)
    p.add_argument("--ticker", default="INOD")
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args()
    result = bind_sec_acceptance(args.report, args.submissions, args.ticker)
    payload = (json.dumps(result, sort_keys=True, indent=2) + "\n").encode()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(payload)
    args.out.with_name(args.out.name + ".sha256").write_text(sha256(payload).hexdigest()+"\n", encoding="ascii")
    print(f"{args.ticker}: {result['partial_legs_bound']} legs, {result['evidence_rows_bound']} source rows bound; canonical scores=0")


if __name__ == "__main__":
    main()
