"""Generate or verify sealed, private S15.3 source and route acceptance audit."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.scoring_v13_s15_gate import audit_report

REPORT = Path.home() / "AppData/Local/S153ResearchTerminal/runtime/scoring_completion/v2_audit2/report.json"
OUTPUT = Path("E:/M10/.master_tasks_v13_private/s15/source_route_audit_v1.json")


def run(*, verify: bool = False) -> dict:
    if REPORT.is_symlink() or Path(str(REPORT) + ".sha256").is_symlink():
        raise ValueError("ORIGINAL_REPORT_SYMLINK_REJECTED")
    result = audit_report(REPORT.read_bytes(), Path(str(REPORT) + ".sha256").read_bytes())
    raw = (json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    digest = sha256(raw).hexdigest()
    seal = Path(str(OUTPUT) + ".sha256")
    if OUTPUT.is_symlink() or seal.is_symlink():
        raise ValueError("PRIVATE_OUTPUT_SYMLINK_REJECTED")
    if verify or OUTPUT.exists() or seal.exists():
        if not OUTPUT.is_file() or not seal.is_file() or OUTPUT.read_bytes() != raw or seal.read_text("ascii").strip() != digest:
            raise ValueError("S15_OFFLINE_REPLAY_OR_SEAL_CHANGED")
    else:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        with OUTPUT.open("xb") as f:
            f.write(raw)
        with seal.open("x", encoding="ascii") as f:
            f.write(digest + "\n")
    return {"task12": result["task12"], "new_accepted_scores": result["new_accepted_S15_3_scores"],
            "dated_market_cap_candidates": result["dated_market_cap_candidates"],
            "private_receipt_sha256": digest, "offline_replay": verify}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    print(json.dumps(run(verify=parser.parse_args().verify), sort_keys=True))
