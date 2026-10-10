"""Synthetic timing fixtures only; never real SEC, news, or alert evidence."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json

import unittest

from app.scoring_event_evidence import (
    audit_sec_acceptance_joins, audit_s16ea_session_evidence, _eastern,
)


def et(year, month, day, hour, minute):
    """Fixed-offset test fixture dates, never a real exchange calendar."""
    hours = -5 if month in (1, 2, 11, 12) else -4
    return datetime(year, month, day, hour, minute,
                    tzinfo=timezone(timedelta(hours=hours)))


AS_OF = et(2026, 10, 9, 9, 34)
CIK = "0000903651"
ACCESSION = "0001104659-26-092021"
ACCEPTED = "2026-08-06T20:15:14Z"


def sec_source():
    return json.dumps({"cik": int(CIK), "filings": {"recent": {
        "accessionNumber": [ACCESSION], "acceptanceDateTime": [ACCEPTED],
        "form": ["10-Q"], "filingDate": ["2026-08-06"],
    }}}).encode()


def fact():
    return {"cik": CIK, "accession": ACCESSION, "source": "SEC_EDGAR",
            "form_type": "10-Q", "filing_date": "2026-08-06",
            "accepted_at": ACCEPTED, "available_at": "2026-08-06T20:20:00Z"}


def bar(at, **changes):
    at = at.astimezone(timezone.utc)
    row = {"timestamp": at.isoformat(), "available_at": (at+timedelta(minutes=1)).isoformat(),
           "exchange_time": _eastern(at).isoformat(),
           "volume": 100.0, "source": "SYNTHETIC_TEST_ONLY", "source_ref": "fixture:minute",
           "evidence_hash": "ab" * 32}
    row.update(changes)
    return row


def news(**changes):
    first = et(2026, 10, 9, 9, 22)
    row = {"first_published_at": first.isoformat(),
           "available_at": (first+timedelta(seconds=5)).isoformat(),
           "first_publication_independently_verified": True,
           "source": "SYNTHETIC_PRIMARY_SOURCE", "source_ref": "fixture:news",
           "evidence_hash": "cd" * 32}
    row.update(changes)
    return row


def sample(route="ZERO_PM_BREAKOUT", *, winter=False):
    dates = [date(2026, 9, 8) + timedelta(days=i) for i in range(30)]
    dates = [d for d in dates if d.weekday() < 5][:20]
    if winter:
        dates[0] = date(2026, 1, 13)
    current = [bar(et(2026, 10, 9, 9, 15))]
    current += [bar(et(2026, 10, 9, 9, minute)) for minute in range(30, 34)]
    history = [bar(et(d.year, d.month, d.day, 9, 33), volume=i + 1)
               for i, d in enumerate(dates)]
    calendar = {"source_ref": "fixture:exchange_calendar", "source_sha256": "ef" * 32,
                "session_dates": [d.isoformat() for d in [*dates, date(2026, 10, 9)]]}
    return {"current_bars": current, "historical_bars": history,
            "news_events": [news()] if route == "NEWS_AT_OPEN" else [],
            "route": route, "evaluated_at": AS_OF, "calendar_evidence": calendar}


def test_sec_acceptance_join_requires_exact_accession_form_and_dates():
    result = audit_sec_acceptance_joins(sec_source(), CIK, [fact()], as_of=AS_OF)
    assert result["status"] == "SEC_ACCEPTANCE_JOIN_REVIEW_ONLY"
    assert result["joins"][0]["join_status"] == "SEC_ADMINISTRATIVE_CLOCK_MATCH"
    assert result["joins"][0]["sec_accepted_at"] == "2026-08-06T20:15:14+00:00"
    assert result["joins"][0]["public_dissemination_at"] is None
    assert result["historical_pit_accepted"] is False
    assert result["canonical_scores_computed"] is False


def test_sec_join_conflicts_block():
    cases = [
        ({"form_type": "10-K"}, "SEC_FORM_MISMATCH"),
        ({"filing_date": "2026-08-07"}, "SEC_FILING_DATE_MISMATCH"),
        ({"available_at": "2026-08-06T20:10:00Z"}, "FACT_AVAILABLE_BEFORE_SEC_ACCEPTANCE"),
        ({"accepted_at": "2026-08-06T20:15:15Z"}, "FACT_ACCEPTANCE_CONFLICT"),
        ({"cik": "1234"}, "FACT_CIK_MISMATCH"),
        ({"accession": "0001104659-26-000001"}, "ACCESSION_NOT_IN_SEC_SOURCE"),
        ({"source": "UNVERIFIED_AGGREGATOR"}, "FACT_NOT_SEC_SOURCED"),
    ]
    for changes, expected in cases:
        result = audit_sec_acceptance_joins(sec_source(), CIK, [dict(fact(), **changes)], as_of=AS_OF)
        assert expected in result["joins"][0]["reasons"]
        assert result["status"].startswith("BLOCKED")


def test_sec_join_rejects_duplicate_accessions_and_naive_acceptance():
    p = json.loads(sec_source())
    for field in ("accessionNumber", "acceptanceDateTime", "form", "filingDate"):
        p["filings"]["recent"][field] *= 2
    with unittest.TestCase().assertRaisesRegex(ValueError, "DUPLICATE"):
        audit_sec_acceptance_joins(json.dumps(p).encode(), CIK, [fact()], as_of=AS_OF)
    p = json.loads(sec_source())
    p["filings"]["recent"]["acceptanceDateTime"] = ["2026-08-06T20:15:14"]
    with unittest.TestCase().assertRaisesRegex(ValueError, "OFFSET_AWARE"):
        audit_sec_acceptance_joins(json.dumps(p).encode(), CIK, [fact()], as_of=AS_OF)


def test_sec_filing_date_later_than_accepted_day_can_still_match():
    p = json.loads(sec_source())
    p["filings"]["recent"]["filingDate"] = ["2026-08-07"]
    result = audit_sec_acceptance_joins(json.dumps(p).encode(), CIK,
                                         [dict(fact(), filing_date="2026-08-07")], as_of=AS_OF)
    assert result["joins"][0]["join_status"] == "SEC_ADMINISTRATIVE_CLOCK_MATCH"
    assert result["historical_pit_accepted"] is False


def test_sec_after_as_of_cannot_be_promoted():
    result = audit_sec_acceptance_joins(sec_source(), CIK, [fact()],
                                        as_of="2026-08-07T23:59:59Z")
    assert "SEC_ACCEPTANCE_AFTER_AS_OF" not in result["joins"][0]["reasons"]
    result = audit_sec_acceptance_joins(sec_source(), CIK, [fact()],
                                        as_of="2026-07-01T00:00:00Z")
    assert result["status"].startswith("BLOCKED")
    assert "SEC_ACCEPTANCE_AFTER_AS_OF" in result["joins"][0]["reasons"]
    assert result["historical_pit_accepted"] is False


def test_s16ea_same_clock_diagnostic_has_no_score_or_alarm():
    result = audit_s16ea_session_evidence(**sample())
    assert result["status"] == "RESEARCH_CLOCK_CANDIDATE_REVIEW_ONLY"
    assert result["baseline_et_minute"] == "09:33"
    assert result["same_clock_sessions"] == 20
    assert result["same_clock_median_volume_diagnostic"] == 10.5
    assert result["score"] is None and result["verified_alarm"] is False
    assert result["historical_pit_accepted"] is False
    assert result["calendar_provenance_independently_verified"] is False


def test_s16ea_daylight_saving_clock_matching_uses_eastern_wall_time():
    result = audit_s16ea_session_evidence(**sample(winter=True))
    assert result["same_clock_sessions"] == 20
    assert result["status"] == "RESEARCH_CLOCK_CANDIDATE_REVIEW_ONLY"


def test_s16ea_requires_real_historical_asof_clocks_and_full_minute_sequence():
    payload = sample()
    payload["current_bars"] = [b for b in payload["current_bars"] if
                               _eastern(datetime.fromisoformat(b["timestamp"])).minute != 31]
    result = audit_s16ea_session_evidence(**payload)
    assert "REGULAR_MINUTE_SEQUENCE_INCOMPLETE" in result["reasons"]
    assert result["same_clock_median_volume_diagnostic"] is None

    payload = sample()
    payload["historical_bars"][0].pop("available_at")
    result = audit_s16ea_session_evidence(**payload)
    assert "OFFSET_AWARE_TIMESTAMP_REQUIRED" in result["reasons"]
    assert "SAME_CLOCK_HISTORY_INSUFFICIENT" in result["reasons"]


def test_s16ea_blocks_duplicate_baseline_dates_and_future_provider_availability():
    payload = sample()
    payload["historical_bars"].append(dict(payload["historical_bars"][0]))
    result = audit_s16ea_session_evidence(**payload)
    assert "DUPLICATE_HISTORICAL_SAME_CLOCK_SESSION" in result["reasons"]
    payload = sample()
    payload["historical_bars"][0]["available_at"] = (AS_OF+timedelta(minutes=10)).isoformat()
    result = audit_s16ea_session_evidence(**payload)
    assert "BAR_FUTURE_LEAKAGE" in result["reasons"]


def test_s16ea_missing_news_first_publication_blocks_news_path():
    payload = sample(route="NEWS_AT_OPEN")
    assert audit_s16ea_session_evidence(**payload)["status"] == "RESEARCH_CLOCK_CANDIDATE_REVIEW_ONLY"
    payload["news_events"][0].pop("first_published_at")
    result = audit_s16ea_session_evidence(**payload)
    assert "OFFSET_AWARE_TIMESTAMP_REQUIRED" in result["reasons"]
    payload = sample(route="NEWS_AT_OPEN")
    payload["news_events"][0]["first_publication_independently_verified"] = False
    result = audit_s16ea_session_evidence(**payload)
    assert "NEWS_FIRST_PUBLICATION_UNVERIFIED" in result["reasons"]


def test_s16ea_future_news_publication_blocks_even_with_attested_source():
    payload = sample(route="NEWS_AT_OPEN")
    payload["news_events"][0]["available_at"] = (AS_OF+timedelta(seconds=1)).isoformat()
    result = audit_s16ea_session_evidence(**payload)
    assert "NEWS_PUBLISHED_AVAILABLE_CLOCK_INVALID" in result["reasons"]
    assert result["verified_alarm"] is False


def test_zero_pm_missing_premarket_cannot_be_called_quiet():
    payload = sample()
    payload["current_bars"] = payload["current_bars"][1:]
    result = audit_s16ea_session_evidence(**payload)
    assert "PREMARKET_OBSERVATIONS_MISSING" in result["reasons"]
    assert result["score"] is None


def test_s16ea_blocks_absent_exchange_calendar_and_uncertified_raw_bars():
    payload = sample()
    payload["calendar_evidence"] = None
    result = audit_s16ea_session_evidence(**payload)
    assert "EXCHANGE_SESSION_CALENDAR_EVIDENCE_MISSING" in result["reasons"]
    payload = sample()
    payload["current_bars"][0].pop("available_at")
    payload["current_bars"][1].pop("source_ref")
    result = audit_s16ea_session_evidence(**payload)
    assert "OFFSET_AWARE_TIMESTAMP_REQUIRED" in result["reasons"]
    assert "BAR_SOURCE_PROVENANCE_MISSING" in result["reasons"]


def test_s16ea_rejects_naive_clock_and_route_outside_window():
    with unittest.TestCase().assertRaisesRegex(ValueError, "OFFSET_AWARE"):
        audit_s16ea_session_evidence(**dict(sample(), evaluated_at="2026-10-09T09:34:00"))
    result = audit_s16ea_session_evidence(**dict(sample(), evaluated_at=AS_OF+timedelta(hours=2)))
    assert "OUTSIDE_S16EA_ROUTE_WINDOW_ET" in result["reasons"]


if __name__ == "__main__":
    suite = unittest.TestSuite(
        unittest.FunctionTestCase(fn, description=name)
        for name, fn in sorted(globals().items())
        if name.startswith("test_") and callable(fn)
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
