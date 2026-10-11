"""Read-only frozen S8 FY2025 evidence, Decimal audit, private SHA replay."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.scoring_v10_s8 import (DEFAULT_BULK, SOURCE_LOCATION, V9_REPORT,
                                audit_sources, verify_private_receipt)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bulk", type=Path, default=DEFAULT_BULK)
    p.add_argument("--v9", type=Path, default=V9_REPORT)
    p.add_argument("--frozen-source", type=Path, default=SOURCE_LOCATION)
    p.add_argument("--out", type=Path, help="NEW private V10 JSON receipt only")
    p.add_argument("--verify", type=Path, help="Offline recompute existing sealed receipt")
    a = p.parse_args(argv)
    if bool(a.out) == bool(a.verify):
        p.error("exactly one of --out or --verify is required")
    path = a.out or a.verify
    private = Path("E:/M10/.scoring_v10_private/s8").resolve()
    resolved = path.resolve()
    if resolved.suffix.lower() != ".json" or private not in resolved.parents:
        raise ValueError("ONLY_ISOLATED_PRIVATE_V10_S8_RECEIPTS_ALLOWED")
    if a.verify:
        packet = verify_private_receipt(resolved, bulk=a.bulk, v9_path=a.v9,
                                        frozen_source=a.frozen_source)
        print(json.dumps({"status": "OFFLINE_REPLAY_PASS", "sha256":
                          sha256(resolved.read_bytes()).hexdigest(),
                          "new_complete_S8_scores": packet["new_complete_S8_scores"]},
                         sort_keys=True))
        return 0
    seal = Path(str(resolved) + ".sha256")
    if (resolved.exists() or resolved.is_symlink() or seal.exists() or seal.is_symlink()):
        raise ValueError("RECEIPT_ALREADY_EXISTS_WILL_NOT_OVERWRITE")
    packet = audit_sources(bulk=a.bulk, v9_path=a.v9, frozen_source=a.frozen_source)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True,
                      allow_nan=False) + "\n").encode("utf8")
    with resolved.open("xb") as out:
        out.write(raw)
    with seal.open("x", encoding="ascii") as out:
        out.write(sha256(raw).hexdigest() + "\n")
    verified = verify_private_receipt(resolved, bulk=a.bulk, v9_path=a.v9,
                                      frozen_source=a.frozen_source)
    print(json.dumps({"status": "OFFLINE_REPLAY_PASS", "sha256":sha256(raw).hexdigest(),
                      "stock_count":len(verified["stocks"]),
                      "new_complete_S8_scores":verified["new_complete_S8_scores"],
                      "FFO_missing": {ticker: entry["FFO_and_FUTL"]["status"]
                                      for ticker, entry in verified["stocks"].items()},
                      "output":str(resolved)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
