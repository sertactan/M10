"""Offline S16-EA real-source gate; absence of first-public and as-of data blocks alerts."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from hashlib import sha256
import json

from app.scoring_intraday_research import parse_minutes, five_minute


def audit_sources(response: bytes, receipt_raw: bytes, bars_raw: bytes,
                  news_report_raw: bytes, news_report_seal: bytes) -> dict:
    receipt = json.loads(receipt_raw)
    if (sha256(response).hexdigest() != receipt.get("sha256") or
            len(response) != receipt.get("bytes") or receipt.get("ticker") != "INOD" or
            receipt.get("http_status") != 200 or receipt.get("provider") != "YAHOO_COMPAT_RESEARCH"):
        raise ValueError("ORIGINAL_INTRADAY_RESPONSE_RECEIPT_CHANGED")
    if news_report_seal.decode("ascii").strip() != sha256(news_report_raw).hexdigest():
        raise ValueError("ORIGINAL_NEWS_CANDIDATE_REPORT_SEAL_CHANGED")
    report = json.loads(news_report_raw)
    issuer = next((s for s in report["stocks"] if s["ticker"] == "INOD"), None)
    if issuer is None:
        raise ValueError("INOD_NEWS_CANDIDATE_SOURCE_MISSING")
    news = issuer.get("sec_event_candidates_v3") or {}
    events = news.get("events") or []
    if news.get("count") != 10 or len(events) != 10 or news.get("status") != "SEC_ACCEPTANCE_EVENT_CANDIDATES_ONLY":
        raise ValueError("ORIGINAL_TEN_SEC_EVENT_CANDIDATES_CHANGED")
    if any(e.get("first_publication_at") is not None or
           e.get("provider_historical_available_at") is not None or
           e.get("timestamp_usable_as_verified_news") is not False for e in events):
        raise ValueError("EVENT_PUBLICATION_STATE_REQUIRES_INDEPENDENT_REVIEW")
    retrieved = datetime.fromisoformat(receipt["retrieved_at"])
    if retrieved.tzinfo is None:
        raise ValueError("INTRADAY_RETRIEVAL_CLOCK_UNZONED")
    parsed, skipped = parse_minutes(json.loads(response), "INOD", retrieved)
    derived = five_minute(parsed)
    saved = json.loads(bars_raw)
    if (saved.get("one_minute") != parsed or saved.get("five_minute") != derived or
            len(parsed) != receipt.get("valid_1m") or len(derived) != receipt.get("complete_derived_5m") or
            skipped != receipt.get("skipped") or
            sum(r["session"] == "PREMARKET_CLOCK" for r in parsed) != receipt.get("premarket_rows")):
        raise ValueError("ORIGINAL_INTRADAY_DERIVATION_CHANGED")
    if any("available_at" in r for r in parsed):
        raise ValueError("UNREVIEWED_BAR_AVAILABLE_AT_CLAIM")
    days = sorted({datetime.fromisoformat(r["exchange_time"]).date().isoformat() for r in parsed})
    if len(days) != 5:
        raise ValueError("ORIGINAL_FIVE_SESSION_WINDOW_CHANGED")
    by_clock = defaultdict(set)
    for r in parsed:
        wall = datetime.fromisoformat(r["exchange_time"])
        by_clock[wall.strftime("%H:%M")].add(wall.date().isoformat())
    last_day = days[-1]
    prior_same_clock = {clock: len(dates - {last_day}) for clock, dates in by_clock.items()
                        if last_day in dates}
    max_prior = max(prior_same_clock.values(), default=0)
    if max_prior > 4:
        raise ValueError("SAME_CLOCK_DISTINCT_SESSION_COUNT_CHANGED")
    if (receipt.get("news_first_public_time") is not None or receipt.get("same_clock_baseline_validated") is not False or
            receipt.get("session_calendar_validated") is not False or receipt.get("exchange_certified") is not False or
            receipt.get("alert_generated") is not False):
        raise ValueError("ORIGINAL_INTRADAY_RESEARCH_GATE_CHANGED")
    return {
        "schema": "V13_S16_EA_OFFLINE_SOURCE_GATE_V1", "ticker": "INOD",
        "response_sha256": sha256(response).hexdigest(),
        "receipt_sha256": sha256(receipt_raw).hexdigest(),
        "derived_bars_sha256": sha256(bars_raw).hexdigest(),
        "news_report_sha256": sha256(news_report_raw).hexdigest(),
        "source_retrieved_at": receipt["retrieved_at"],
        "one_minute_rows": len(parsed), "derived_five_minute_rows": len(derived),
        "premarket_clock_rows": receipt["premarket_rows"],
        "ET_dates": days, "max_prior_same_clock_dates_for_latest_session": max_prior,
        "minimum_same_clock_sessions": 20,
        "minimum_additional_prior_sessions_needed": max(0, 20 - max_prior),
        "SEC_8K_event_candidates": len(events),
        "independently_verified_first_public_events": 0,
        "historical_provider_arrivals": 0,
        "bar_historical_available_at_rows": 0,
        "exchange_calendar_validated": False,
        "independent_five_minute_provider_series": False,
        "missing_acceptance": [
            "INDEPENDENT_FIRST_PUBLICATION_UTC_AND_PROVIDER_ARRIVAL",
            "BAR_LEVEL_HISTORICAL_AVAILABLE_AT",
            "TWENTY_PRIOR_SAME_CLOCK_SESSIONS",
            "CERTIFIED_EXCHANGE_SESSION_CALENDAR_AND_INTRADAY_SOURCE",
            "INDEPENDENT_1M_5M_AS_OF_REPLAY_AND_OUTCOME_LABELS",
        ],
        "status": "BLOCKED_MISSING_HISTORICAL_EVENT_AND_MARKET_EVIDENCE",
        "verified_alerts": 0, "hit_miss_false_positive_evaluated": False,
        "S16_EA_score": None, "task16": "PARTIAL",
    }
