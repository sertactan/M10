#!/usr/bin/env python3
"""Prospective Social V5 PIT capture, isolated from canonical Meridyen models.

No retrospective reconstruction of observed_at, sentiment, alerts or prices.
Stores *hashed identifiers only* in the public M10 experimental branch.
Python stdlib; one Bluesky GET and one Mastodon public hashtag GET per run.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
from urllib.request import Request, build_opener

import social_v5_free as core

_MAX_POSTS = 15
_HISTORY_DAYS_FOR_DEDUP = 8
_MAX_FILE_BYTES = 3_000_000
_SCHEMA_VERSION = "SOCIAL_PIT_V1_RESEARCH_NONCANONICAL"


def appview_fetch(original_url):
    prefix = "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts?"
    if not original_url.startswith(prefix):
        raise ValueError("Only the official Bluesky public search endpoint is permitted")
    url = "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts?" + original_url[len(prefix):]
    req = Request(url, headers={
        "User-Agent": "MeridyenSocialPIT/0.1 (keyless research, no streaming)",
        "Accept": "application/json",
    })
    with build_opener(core._NoRedirect()).open(req, timeout=8) as res:
        if res.status != 200:
            raise RuntimeError("public Bluesky status " + str(res.status))
        data = res.read(core.LIMIT_BYTES + 1)
        if len(data) > core.LIMIT_BYTES:
            raise ValueError("public response exceeds fixed byte cap")
        return json.loads(data.decode("utf-8"))


def anonymized_post(row, ticker, run_id):
    event = core.verified_event(row)
    if event["ticker"] != ticker or event["capture_proof"] != "public_network_capture":
        raise ValueError("PIT capture requires exact ticker and public network proof")
    return {
        "schema": _SCHEMA_VERSION,
        "ticker": ticker,
        "platform": event["platform"],
        "source_id_hash": core.sha(event["platform"] + "|" + event["source_id"]),
        "source_url_hash": core.sha(event["source_url"]),
        "text_hash": event["text_hash"],
        "author_hash": event["author_hash"],
        "created_at": event["created_at"],
        "first_observed_at": event["observed_at"],
        "capture_proof": "public_network_capture",
        "engagement_at_first_observation": event["engagement"],
        "run_id": run_id,
    }


def _read_jsonl(path):
    if not path.exists():
        return []
    if path.stat().st_size > _MAX_FILE_BYTES:
        raise ValueError("refusing oversized PIT file")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _append_jsonl(path, entries):
    if not entries:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    old = path.read_text(encoding="utf-8") if path.exists() else ""
    if len(old.encode("utf-8")) > _MAX_FILE_BYTES:
        raise ValueError("refusing oversized PIT file")
    added = "".join(json.dumps(e, ensure_ascii=False, sort_keys=True) + "\n" for e in entries)
    if len(old.encode("utf-8")) + len(added.encode("utf-8")) > _MAX_FILE_BYTES:
        raise ValueError("new PIT file exceeds size cap")
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(old + added, encoding="utf-8")
    os.replace(tmp, path)


def record_capture(store, ticker, fetched_rows, run_id, now):
    """Append first-seen events; never revise an earlier observation timestamp."""
    store = Path(store)
    ticker = core.valid_symbol(ticker)
    current = core.stamp(now)
    # GitHub Actions provides independent commit/run evidence but not exact API timing proof.
    seen = set()
    for index in range(_HISTORY_DAYS_FOR_DEDUP):
        day = (current - dt.timedelta(days=index)).date().isoformat()
        for old in _read_jsonl(store / (day + ".jsonl")):
            seen.add((old["platform"], old["source_id_hash"], old["ticker"]))
    fresh = []
    for row in fetched_rows:
        item = anonymized_post(row, ticker, str(run_id))
        observed = core.stamp(item["first_observed_at"])
        created = core.stamp(item["created_at"])
        if observed > current + dt.timedelta(seconds=2) or created > observed:
            raise ValueError("invalid observation chronology")
        key = (item["platform"], item["source_id_hash"], item["ticker"])
        if key not in seen:
            fresh.append(item)
            seen.add(key)
    path = store / (current.date().isoformat() + ".jsonl")
    _append_jsonl(path, fresh)
    return {"new_first_seen":len(fresh), "target":str(path), "total_candidates":len(fetched_rows)}


def capture(ticker, store, run_id="manual"):
    ticker = core.valid_symbol(ticker)
    rows = []
    sources = {}
    started = core.iso(dt.datetime.now(dt.timezone.utc))
    for platform, getter in (
        ("bluesky", lambda: core.collect_bluesky(ticker, limit=_MAX_POSTS, fetch=appview_fetch)),
        ("mastodon", lambda: core.collect_mastodon(ticker, instance="mastodon.social", hashtag="stocks", limit=_MAX_POSTS)),
    ):
        try:
            items = getter()
            sources[platform] = {"status": "OK", "matched": len(items)}
            rows.extend(items)
        except Exception as exc:
            # Record failure explicitly; NEVER assume zero observed posts = no interest.
            sources[platform] = {"status": "PUBLIC_SOURCE_UNAVAILABLE", "error_type": type(exc).__name__}
    ended = core.iso(dt.datetime.now(dt.timezone.utc))
    result = record_capture(store, ticker, rows, run_id, ended)
    run = {
        "schema": _SCHEMA_VERSION, "ticker": ticker, "run_id": str(run_id),
        "capture_started_at": started, "capture_ended_at": ended,
        "sources": sources, **result, "is_trade_signal": False,
        "s16_e": "NOT_COMPUTED", "s16_c": "NOT_COMPUTED",
    }
    # Separate provenance log: includes outage and zero-match runs.
    _append_jsonl(Path(store) / "capture_runs.jsonl", [run])
    return run


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", default="INOD")
    parser.add_argument("--store", default="social-v5-render/pit_data")
    parser.add_argument("--run-id", default=os.getenv("GITHUB_RUN_ID", "manual"))
    a = parser.parse_args()
    print(json.dumps(capture(a.ticker, a.store, a.run_id), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
