"""Read-only replay of seven historical INOD SEC administrative clock joins."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.scoring_v13_pit_reconcile import reconcile


def seal_or_verify(path: Path, data: bytes, *, verify: bool) -> str:
    digest = sha256(data).hexdigest()
    sidecar = path.with_name(path.name + ".sha256")
    if verify:
        if path.read_bytes() != data or sidecar.read_text(encoding="ascii") != digest + "\n":
            raise ValueError("PIT_REPLAY_OR_SHA_MISMATCH")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as handle:
            handle.write(data)
        with sidecar.open("x", encoding="ascii", newline="\n") as handle:
            handle.write(digest + "\n")
    return digest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submissions", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--phase24k", type=Path, required=True)
    parser.add_argument("--phase24m", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    report = reconcile(args.submissions.read_bytes(), args.receipt.read_bytes(),
                       args.phase24k.read_bytes(), args.phase24m.read_bytes())
    data = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
    digest = seal_or_verify(args.out, data, verify=args.verify)
    print(json.dumps({"administrative_joins_verified": report["administrative_joins_verified"],
                      "canonical_pit_versions": report["canonical_pit_versions"],
                      "report_sha256": digest, "verified": args.verify}))


if __name__ == "__main__":
    main()
