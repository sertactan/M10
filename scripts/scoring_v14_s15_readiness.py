"""Seal or replay a private, read-only S15.3 source inventory."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.scoring_v14_s15_readiness import audit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    result = audit(args.report, args.db)
    raw = (json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    digest = sha256(raw).hexdigest()
    sidecar = Path(str(args.out) + ".sha256")
    if args.verify:
        if args.out.read_bytes() != raw or sidecar.read_text("ascii").strip() != digest:
            raise ValueError("PRIVATE_S15_RECEIPT_CHANGED")
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("xb") as stream:
            stream.write(raw)
        with sidecar.open("x", encoding="ascii") as stream:
            stream.write(digest + "\n")
    print(json.dumps({"status": result["task12"], "verified_gates": [],
                      "receipt_sha256": digest, "offline_replay": args.verify}, sort_keys=True))


if __name__ == "__main__":
    main()
