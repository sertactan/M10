"""Replay sealed V13 minute/news evidence and Nasdaq scheduled-date gate."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.scoring_v13_event_gate import audit_sources
from app.scoring_v14_event_calendar import audit_calendar

PROBE = Path.home() / "AppData/Local/S153ResearchTerminal/runtime/scoring_completion/intraday_probe"
NEWS_REPORT = Path("E:/M10/.scoring_v9_private/scoring_completion/v9_research_report.json")
V13 = Path("E:/M10/.master_tasks_v13_private/event/inod_event_source_gate_v1.json")
OUT = Path("E:/M10/.master_tasks_v14_private/event/inod_nasdaq_calendar_gate_v1.json")


def run(*, verify: bool = False) -> dict:
    sources = (PROBE / "response.json", PROBE / "receipt.json", PROBE / "bars.json",
               NEWS_REPORT, Path(str(NEWS_REPORT) + ".sha256"))
    if any(path.is_symlink() for path in (*sources, V13, Path(str(V13) + ".sha256"))):
        raise ValueError("SOURCE_SYMLINK_REJECTED")
    prior = audit_sources(*(path.read_bytes() for path in sources))
    prior_raw = V13.read_bytes()
    prior_sha = sha256(prior_raw).hexdigest()
    if (Path(str(V13) + ".sha256").read_text("ascii").strip() != prior_sha or
            json.loads(prior_raw) != prior):
        raise ValueError("V13_ORIGINAL_EVENT_SOURCE_REPLAY_OR_SEAL_CHANGED")
    result = audit_calendar(prior)
    result["v13_source_gate_sha256"] = prior_sha
    result["original_response_sha256"] = prior["response_sha256"]
    raw = (json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()
    digest = sha256(raw).hexdigest()
    seal = Path(str(OUT) + ".sha256")
    if OUT.is_symlink() or seal.is_symlink():
        raise ValueError("PRIVATE_OUTPUT_SYMLINK_REJECTED")
    if verify or OUT.exists() or seal.exists():
        if not OUT.is_file() or not seal.is_file() or OUT.read_bytes() != raw or seal.read_text("ascii").strip() != digest:
            raise ValueError("V14_EVENT_OFFLINE_REPLAY_OR_SEAL_CHANGED")
    else:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        with OUT.open("xb") as f:
            f.write(raw)
        with seal.open("x", encoding="ascii") as f:
            f.write(digest + "\n")
    return {"task16": result["task16"], "official_schedule_dates_open": result["official_schedule_dates_open"],
            "missing_prior_scheduled_sessions": len(result["missing_prior_scheduled_sessions"]),
            "verified_alerts": result["verified_alerts"], "receipt_sha256": digest,
            "offline_replay": verify}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    print(json.dumps(run(verify=parser.parse_args().verify), sort_keys=True))
