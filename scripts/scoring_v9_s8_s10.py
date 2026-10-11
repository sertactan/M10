"""Offline S8/S10 original-source partial computation over immutable V8 SEC pins."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.scoring_v9_s8_s10 import SOURCE_LOCATION, audit_bulk


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bulk", type=Path, default=Path(os.environ.get("LOCALAPPDATA", "")) /
                        "S153ResearchTerminal/runtime/bulk/sec/companyfacts.zip",
                        help="Existing, privately cached SEC bulk archive")
    parser.add_argument("--frozen-source", type=Path, default=SOURCE_LOCATION,
                        help="Original plugin contract; exact SHA pinned")
    parser.add_argument("--out", type=Path, required=True,
                        help="NEW private V9 receipt; refuses overwrite")
    args = parser.parse_args(argv)
    target = args.out.resolve()
    private = (Path("E:/M10/.scoring_v9_private/s8_s10")).resolve()
    seal_path = Path(f"{target}.sha256")
    if (target.suffix.lower() != ".json" or target.exists() or target.is_symlink()
            or seal_path.exists() or seal_path.is_symlink() or private not in target.parents):
        raise ValueError("NEW_V9_PRIVATE_S8_S10_RECEIPT_REQUIRED")
    result = audit_bulk(args.bulk, args.frozen_source)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    with target.open("xb") as dest:
        dest.write(data)
    with seal_path.open("x", encoding="ascii") as dest:
        dest.write(sha256(data).hexdigest() + "\n")
    print(json.dumps({
        "status": "RESEARCH_PARTIAL",
        "pinned_members_revalidated": result["pinned_V8_members_revalidated"],
        "frozen_sha256": result["frozen_source_sha256"],
        "S8_full_scores": 0, "S10_full_scores": 0,
        "S8_size_by_company": {
            ticker: {year: data["ohlson"].get("size", {}).get("SIZE")
                     for year, data in stock["S8"]["years"].items()}
            for ticker, stock in result["stocks"].items()},
        "CRMD_2021_receivables": result["stocks"]["CRMD"]["S10"]
                                ["crmd_targeted_receivables"]
                                ["FY2021_net_receivables_fallback"].get("value"),
        "private_receipt": str(target), "receipt_sha256": sha256(data).hexdigest(),
        "network_requests": result["network_requests"],
    }, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
