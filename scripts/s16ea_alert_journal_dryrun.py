"""Research-only dry-run journal for a potential future S16-EA cloud worker.

NO network polling, push notifications, signal calculation, trades, cron or
auto-deployment. Writes an append-only event journal only when explicitly run
with --journal. Never claims market coverage or canonical data certification.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from scripts.s16ea_cloud_evidence_gate import assess
from scripts.mobile_provider_evidence import instant

SCHEMA = "MERIDYEN_S16EA_RESEARCH_JOURNAL_V1"


def fingerprint(payload):
    ticker = str(payload.get("ticker", "")).upper().strip()
    route = str(payload.get("route", ""))
    timestamp = instant(payload["as_of"]).isoformat()
    return hashlib.sha256((ticker + "|" + route + "|" + timestamp).encode()).hexdigest()


def record(payload, journal, *, dry_run=True):
    """Never emit trade alerts, even if user attests to full coverage."""
    result = assess(payload)
    if result["status"] != "RESEARCH_INPUT_GATES_PRESENT_ONLY":
        return {"status": "BLOCKED", "reasons": result["reasons"],
                "recorded": False, "notification_sent": False}
    fid = fingerprint(payload)
    path = Path(journal)
    if path.is_file():
        with path.open(encoding="utf-8") as file:
            for line in file:
                if not line.strip():
                    continue
                current = json.loads(line)
                if current.get("event_id") == fid:
                    return {"status": "RESEARCH_DUPLICATE", "recorded": False,
                            "event_id": fid, "notification_sent": False}
    row = {"schema": SCHEMA, "event_id": fid, "ticker": str(payload["ticker"]).upper(),
           "route": payload["route"], "as_of": instant(payload["as_of"]).isoformat(),
           "evidence_status": result["status"], "canonical_ready": False,
           "s16_e": "NOT_COMPUTED", "s16_c": "INCONCLUSIVE",
           "s16_ea": "NOT_COMPUTED", "is_trade_signal": False,
           "notification_sent": False, "source_coverage_independently_verified": False}
    if dry_run:
        return {"status": "RESEARCH_DRY_RUN", "recorded": False,
                "event_id": fid, "notification_sent": False}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return {"status": "RESEARCH_RECEIPT_RECORDED", "recorded": True,
            "event_id": fid, "notification_sent": False}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--input",required=True)
    parser.add_argument("--journal",required=True)
    parser.add_argument("--record",action="store_true",help="Append research-only receipt")
    opts=parser.parse_args()
    value=record(json.loads(Path(opts.input).read_text(encoding="utf-8")),
                 opts.journal,dry_run=not opts.record)
    print(json.dumps(value,sort_keys=True))
    return 2 if value["status"]=="BLOCKED" else 0


if __name__=="__main__":
    raise SystemExit(main())
