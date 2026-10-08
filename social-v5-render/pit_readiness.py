#!/usr/bin/env python3
"""Noncanonical PIT coverage health. Never infer absence of posts from missing snapshots.

Requires 72 baseline hours plus 24 current hours of recurring SOURCE_OK captures.
An isolated initial capture ALWAYS stays NOT_READY even if it contains many posts.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
import social_v5_free as core

SOURCE_NAMES = ("bluesky", "mastodon")
BASE_HOURS = 72
CURRENT_HOURS = 24
# Research-only QA coverage gates, NOT any Meridyen S15 or S16 rule.
REQUIRED_FRACTION = .90


def readiness(run_file, as_of):
    now = core.stamp(as_of)
    start = now - dt.timedelta(hours=BASE_HOURS + CURRENT_HOURS)
    recent = now - dt.timedelta(hours=CURRENT_HOURS)
    statuses = {p: {"baseline": set(), "current": set()} for p in SOURCE_NAMES}
    f = Path(run_file)
    rows = [] if not f.exists() else [
        json.loads(line) for line in f.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    for item in rows:
        if item.get("schema") != "SOCIAL_PIT_V1_RESEARCH_NONCANONICAL":
            continue
        capture = core.stamp(item["capture_ended_at"])
        if not start <= capture <= now:
            continue
        bucket = capture.replace(minute=0, second=0, microsecond=0).isoformat()
        window = "current" if capture >= recent else "baseline"
        for source in SOURCE_NAMES:
            if item.get("sources", {}).get(source, {}).get("status") == "OK":
                statuses[source][window].add(bucket)
    coverage = {
        name: {
            "baseline_observed_hours": len(group["baseline"]),
            "current_observed_hours": len(group["current"]),
            "required_baseline_hours": 65,
            "required_current_hours": 22,
        }
        for name, group in statuses.items()
    }
    good = any(v["baseline_observed_hours"] >= 65 and
               v["current_observed_hours"] >= 22 for v in coverage.values())
    return {
        "module": "MERIDYEN_SOCIAL_PIT_PHASE3", "as_of": core.iso(now),
        "status": "RESEARCH_BASELINE_ELIGIBLE_NONCANONICAL" if good else "BASELINE_NOT_READY",
        "source_coverage": coverage,
        "note": "Sampling coverage only, not representative market coverage; 72+24 elapsed hours required",
        "trade_signal": False,
        "s15_s16": "UNCHANGED_NOT_COMPUTED",
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--runs", default="social-v5-render/pit_data/capture_runs.jsonl")
    p.add_argument("--as-of", default=core.iso(dt.datetime.now(dt.timezone.utc)))
    p.add_argument("--output", default="")
    args = p.parse_args()
    r = readiness(args.runs, args.as_of)
    data = json.dumps(r, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(data, encoding="utf-8")
    print(data)


if __name__ == "__main__":
    main()
