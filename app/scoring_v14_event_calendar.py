"""Nasdaq 2026 scheduled-session audit for the sealed INOD S16-EA source window.

The holiday dates below are transcribed from Nasdaq Trader's published 2026
U.S. equity calendar. They establish scheduled dates only: they do not attest
individual minute bars, provider arrival times, halts, or first news release.
"""
from __future__ import annotations

from datetime import date, timedelta

CALENDAR_URL = "https://www.nasdaqtrader.com/Trader.aspx?id=Calendar"
CLOSED_2026 = frozenset(date.fromisoformat(s) for s in (
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03",
    "2026-05-25", "2026-06-19", "2026-07-03", "2026-09-07",
    "2026-11-26", "2026-12-25",
))
EARLY_CLOSE_2026 = frozenset(date.fromisoformat(s) for s in (
    "2026-11-27", "2026-12-24",
))


def scheduled_open(day: date) -> bool:
    if day.year != 2026:
        raise ValueError("NASDAQ_2026_CALENDAR_SCOPE_ONLY")
    return day.weekday() < 5 and day not in CLOSED_2026


def prior_scheduled_sessions(day: date, count: int = 20) -> tuple[date, ...]:
    if not scheduled_open(day) or count != 20:
        raise ValueError("TWENTY_PRIOR_OPEN_SESSIONS_REQUIRED")
    result = []
    cursor = day - timedelta(days=1)
    while len(result) < count:
        if scheduled_open(cursor):
            result.append(cursor)
        cursor -= timedelta(days=1)
    return tuple(reversed(result))


def audit_calendar(v13: dict) -> dict:
    if (v13.get("schema") != "V13_S16_EA_OFFLINE_SOURCE_GATE_V1" or
            v13.get("ticker") != "INOD" or v13.get("verified_alerts") != 0 or
            v13.get("S16_EA_score") is not None or
            v13.get("max_prior_same_clock_dates_for_latest_session") != 4):
        raise ValueError("SOURCE_EVENT_GATE_CHANGED")
    observed = tuple(date.fromisoformat(s) for s in v13["ET_dates"])
    if len(observed) != 5 or len(set(observed)) != 5 or tuple(sorted(observed)) != observed:
        raise ValueError("OBSERVED_ET_DATE_WINDOW_INVALID")
    if any(not scheduled_open(day) for day in observed):
        raise ValueError("SOURCE_BAR_ON_NASDAQ_CLOSED_DATE")
    target = observed[-1]
    required = prior_scheduled_sessions(target)
    covered = tuple(day for day in required if day in observed[:-1])
    missing = tuple(day for day in required if day not in observed[:-1])
    if len(covered) != 4 or len(missing) != 16:
        raise ValueError("SOURCE_PRIOR_SCHEDULED_SESSION_COVERAGE_CHANGED")
    return {
        "schema": "V14_S16_EA_NASDAQ_DATE_SCHEDULE_AUDIT_V1",
        "ticker": "INOD", "evaluation_ET_date": target.isoformat(),
        "nasdaq_2026_calendar_source": CALENDAR_URL,
        "official_schedule_checked_dates": [d.isoformat() for d in observed],
        "official_schedule_dates_open": True,
        "calendar_source_raw_byte_sealed": False,
        "required_20_prior_scheduled_sessions": [d.isoformat() for d in required],
        "source_covered_prior_sessions": [d.isoformat() for d in covered],
        "missing_prior_scheduled_sessions": [d.isoformat() for d in missing],
        "source_max_same_clock_prior_dates": 4,
        "same_clock_baseline_accepted": False,
        "historical_bar_available_at_verified": False,
        "historical_news_first_public_and_provider_arrival_verified": False,
        "independent_1m_and_5m_source_pair_verified": False,
        "exchange_intraday_bars_certified": False,
        "verified_alerts": 0, "S16_EA_score": None,
        "task16": "PARTIAL",
    }
