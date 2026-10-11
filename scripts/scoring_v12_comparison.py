"""Create or replay the private, source-verified five-stock comparison."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.scoring_v12_comparison import build_comparison, canonical_bytes

ROOT = Path("E:/M10/.master_tasks_v12_private/comparison")
OUTPUT = ROOT / "five_stock_v2.json"


def run(verify: bool) -> dict:
    runtime = Path(os.environ["LOCALAPPDATA"]) / "S153ResearchTerminal/runtime"
    report = build_comparison(runtime / "phase27/current_scoring/staging.db",
                              runtime / "phase28/real_scoring_v1/stage.db")
    raw = canonical_bytes(report)
    digest = sha256(raw).hexdigest()
    seal = Path(str(OUTPUT) + ".sha256")
    if OUTPUT.is_symlink() or seal.is_symlink():
        raise ValueError("SYMLINK_PRIVATE_RECEIPT_NOT_ALLOWED")
    if verify:
        if OUTPUT.read_bytes() != raw or seal.read_text("ascii").strip() != digest:
            raise ValueError("V12_FIVE_STOCK_OFFLINE_REPLAY_FAILED")
    else:
        ROOT.mkdir(parents=True, exist_ok=True)
        with OUTPUT.open("xb") as f:
            f.write(raw)
        with seal.open("x", encoding="ascii") as f:
            f.write(digest + "\n")
    return {"status": "OFFLINE_REPLAY_PASS" if verify else "SOURCE_SEALED",
            "receipt_sha256": digest, "full_research_scores": report["full_research_scores"],
            "canonical_pit_features": report["canonical_pit_features"],
            "stocks": len(report["stocks"])}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args.verify), sort_keys=True))
