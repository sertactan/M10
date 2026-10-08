"""Fail-closed cloud research evidence gate for S16-EA V1.3 (NOT the frozen scorer).

No API calls, order execution, schedules, alerts, score substitution or hidden data
reconstruction. An external worker may call this before passing as-of evidence
to the original separately versioned S16-EA engine.
"""
import argparse
import datetime as dt
import json
from pathlib import Path

VERSION = "S16EA_CLOUD_EVIDENCE_GATE_V1"
ROUTES = {"NEWS_AT_OPEN", "ZERO_PM_BREAKOUT"}


def parsed_time(value):
    if not isinstance(value, str):
        raise ValueError("timestamp missing")
    value = value.replace("Z", "+00:00")
    parsed = dt.datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("naive timestamp blocked")
    return parsed.astimezone(dt.timezone.utc)


def assess(payload):
    """Classify only temporal and capture evidence; never derive canonical weights."""
    errors = []
    route = payload.get("route")
    ticker = str(payload.get("ticker") or "").strip().upper()
    if route not in ROUTES:
        errors.append("INVALID_ROUTE")
    if not ticker or len(ticker) > 10 or not all(x.isalnum() or x in ".-" for x in ticker):
        errors.append("INVALID_SYMBOL")
    try:
        as_of = parsed_time(payload.get("as_of"))
    except (ValueError, TypeError):
        errors.append("INVALID_AS_OF")
        as_of = None

    bars = payload.get("intraday_bars", [])
    news = payload.get("news_events", [])
    if not isinstance(bars, list) or not bars:
        errors.append("MISSING_TIMESTAMPED_INTRADAY")
        bars = []
    if not isinstance(news, list):
        errors.append("INVALID_NEWS_EVENTS")
        news = []

    for category, items in (("INTRADAY", bars), ("NEWS", news)):
        for i, item in enumerate(items):
            if not isinstance(item, dict) or not item.get("source") or not item.get("source_ref"):
                errors.append(f"{category}_{i}_MISSING_PROVENANCE")
                continue
            try:
                observed = parsed_time(item.get("observed_at"))
                available = parsed_time(item.get("available_at"))
            except (ValueError, TypeError):
                errors.append(f"{category}_{i}_INVALID_TIMESTAMP")
                continue
            if available < observed:
                errors.append(f"{category}_{i}_AVAILABLE_BEFORE_OBSERVED")
            if as_of and (observed > as_of or available > as_of):
                errors.append(f"{category}_{i}_FUTURE_LEAKAGE")
            if category == "INTRADAY" and item.get("interval_minutes") not in (1, 5):
                errors.append(f"{category}_{i}_NOT_1M_OR_5M")

    if route == "NEWS_AT_OPEN" and not news:
        errors.append("MISSING_NEWS_AT_OPEN_EVIDENCE")
    if payload.get("coverage_verified") is not True:
        errors.append("INTRADAY_SOURCE_COVERAGE_UNVERIFIED")
    if payload.get("historical_baseline_verified") is not True:
        errors.append("HISTORICAL_BASELINE_UNVERIFIED")

    return {
        "version": VERSION, "ticker": ticker, "as_of": payload.get("as_of"),
        "route": route, "status": "BLOCKED_MISSING_OR_INVALID_EVIDENCE" if errors else "RESEARCH_INPUT_GATES_PRESENT_ONLY",
        "reasons": sorted(set(errors)), "intraday_records": len(bars), "news_records": len(news),
        "canonical_scores_computed": False, "s16_e": "NOT_COMPUTED",
        "s16_c": "INCONCLUSIVE", "s16_ea": "NOT_COMPUTED",
        "is_trade_signal": False, "notification_sent": False,
        "note": "Coverage attestations are caller-provided, not independently audited. This is NOT a model score, live alarm or production PIT certification.",
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--output")
    args = p.parse_args()
    result = assess(json.loads(Path(args.input).read_text(encoding="utf-8")))
    out = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(out + "\n", encoding="utf-8")
    else:
        print(out)
    return 2 if result["status"].startswith("BLOCKED") else 0


if __name__ == "__main__":
    raise SystemExit(main())
