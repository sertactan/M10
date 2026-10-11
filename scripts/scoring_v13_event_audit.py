"""Seal or replay the real INOD event/minute source gate without an alert."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.scoring_v13_event_gate import audit_sources

PROBE = Path.home() / "AppData/Local/S153ResearchTerminal/runtime/scoring_completion/intraday_probe"
NEWS_REPORT = Path("E:/M10/.scoring_v9_private/scoring_completion/v9_research_report.json")
OUT = Path("E:/M10/.master_tasks_v13_private/event/inod_event_source_gate_v1.json")


def run(*, verify: bool = False) -> dict:
    paths = (PROBE / "response.json", PROBE / "receipt.json", PROBE / "bars.json",
             NEWS_REPORT, Path(str(NEWS_REPORT) + ".sha256"))
    if any(path.is_symlink() for path in paths):
        raise ValueError("SOURCE_SYMLINK_REJECTED")
    result = audit_sources(*(path.read_bytes() for path in paths))
    raw = (json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()
    digest = sha256(raw).hexdigest()
    seal = Path(str(OUT) + ".sha256")
    if OUT.is_symlink() or seal.is_symlink():
        raise ValueError("PRIVATE_OUTPUT_SYMLINK_REJECTED")
    if verify or OUT.exists() or seal.exists():
        if not OUT.is_file() or not seal.is_file() or OUT.read_bytes() != raw or seal.read_text("ascii").strip() != digest:
            raise ValueError("V13_EVENT_OFFLINE_REPLAY_OR_SEAL_FAILED")
    else:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        with OUT.open("xb") as f:
            f.write(raw)
        with seal.open("x", encoding="ascii") as f:
            f.write(digest + "\n")
    return {"task16": result["task16"], "verified_alerts": result["verified_alerts"],
            "latest_session_max_prior_same_clock": result["max_prior_same_clock_dates_for_latest_session"],
            "receipt_sha256": digest, "offline_replay": verify}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    print(json.dumps(run(verify=parser.parse_args().verify), sort_keys=True))
