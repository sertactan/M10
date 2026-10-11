"""Seal or verify an offline S16-E real-pilot OOS readiness audit."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.scoring_v13_estimated_oos import audit_real_pilot


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot", type=Path, required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    report = audit_real_pilot(args.pilot.read_bytes(), evaluation_as_of=args.as_of)
    data = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
    digest = sha256(data).hexdigest()
    sidecar = args.out.with_name(args.out.name + ".sha256")
    if args.verify:
        if args.out.read_bytes() != data or sidecar.read_text(encoding="ascii") != digest + "\n":
            raise ValueError("S16E_OOS_REPORT_REPLAY_MISMATCH")
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("xb") as handle:
            handle.write(data)
        with sidecar.open("x", encoding="ascii", newline="\n") as handle:
            handle.write(digest + "\n")
    print(json.dumps({"pilot_security_count": report["pilot_security_count"],
                      "eligible_oos_cases": report["eligible_oos_cases"],
                      "metrics": report["metrics"], "report_sha256": digest,
                      "verified": args.verify}))


if __name__ == "__main__":
    main()
