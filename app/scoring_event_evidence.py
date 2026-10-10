"""Offline, fail-closed SEC and S16-EA event-clock evidence reviews.

Pure research diagnostics: no network, database, model execution, score, alarm,
or claim of certified public dissemination. Caller-provided source attestations
and calendar lists cannot independently establish historical PIT availability.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
import math
import re
from statistics import median
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


VERSION = "M10_SCORING_EVENT_EVIDENCE_REVIEW_V1"
try:
    NY = ZoneInfo("America/New_York")
except ZoneInfoNotFoundError:
    NY = None
ACCESSION = re.compile(r"\d{10}-\d{2}-\d{6}\Z")
SHA256 = re.compile(r"[a-fA-F0-9]{64}\Z")
SEC_FACT_SOURCES = {"SEC_EDGAR", "SEC_EDGAR_LOCAL_ARCHIVE_ACCEPTED_UNVERIFIED"}
ROUTES = {"NEWS_AT_OPEN", "ZERO_PM_BREAKOUT"}


def _eastern(value: datetime) -> datetime:
    """ET wall clock, guarded if Windows Python lacks a timezone database.

    Only the 2024–2026 research window has a fallback. Its 2007-era US DST
    transition calculation is a clock candidate, never an exchange calendar.
    Other years require actual IANA timezone data and fail closed.
    """
    at = _utc(value)
    if NY is not None:
        return at.astimezone(NY)
    if at.year not in (2024, 2025, 2026):
        raise ValueError("NY_TZDATA_UNAVAILABLE_OUTSIDE_SUPPORTED_RESEARCH_WINDOW")
    march = date(at.year, 3, 1)
    november = date(at.year, 11, 1)
    second_sunday_march = 1 + (6 - march.weekday()) % 7 + 7
    first_sunday_november = 1 + (6 - november.weekday()) % 7
    start = datetime(at.year, 3, second_sunday_march, 7, tzinfo=timezone.utc)
    end = datetime(at.year, 11, first_sunday_november, 6, tzinfo=timezone.utc)
    offset = -4 if start <= at < end else -5
    return at.astimezone(timezone(timedelta(hours=offset)))


def _utc(value: str | datetime) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("INVALID_TIMESTAMP") from exc
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("OFFSET_AWARE_TIMESTAMP_REQUIRED")
    return value.astimezone(timezone.utc)


def _cik(value: object) -> int:
    if isinstance(value, bool) or not re.fullmatch(r"\d{1,10}", str(value)):
        raise ValueError("INVALID_CIK")
    return int(str(value))


def audit_sec_acceptance_joins(
    submissions_raw: bytes, cik: str, facts: list[dict], *, as_of: str | datetime
) -> dict:
    """Join cached SEC acceptance clocks to facts; never infer dissemination.

    Original bytes are hashed, avoiding reliance on an unchecked user-supplied
    hash. An exact accession/form/filing-date match is an administrative clock
    match, not historical source availability or the first public release.
    """
    clock = _utc(as_of)
    issuer = _cik(cik)
    if not isinstance(submissions_raw, bytes) or len(submissions_raw) > 10_000_000:
        raise ValueError("SEC_BYTES_REQUIRED_AND_BOUNDED")
    try:
        payload = json.loads(submissions_raw)
        if not isinstance(payload, dict) or _cik(payload.get("cik")) != issuer:
            raise ValueError("SEC_ISSUER_MISMATCH")
        recent = payload["filings"]["recent"]
        fields = ("accessionNumber", "acceptanceDateTime", "form", "filingDate")
        arrays = [recent[k] for k in fields]
        if not all(isinstance(x, list) for x in arrays) or len({len(x) for x in arrays}) != 1:
            raise ValueError("SEC_PARALLEL_ARRAYS_INVALID")
    except (TypeError, KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("SEC_SOURCE_INVALID") from exc

    indexed = {}
    for accession, accepted_raw, form, filing_raw in zip(*arrays):
        if not isinstance(accession, str) or not ACCESSION.fullmatch(accession):
            raise ValueError("SEC_ACCESSION_INVALID")
        if accession in indexed:
            raise ValueError("SEC_DUPLICATE_ACCESSION_AMBIGUOUS")
        accepted = _utc(accepted_raw)
        try:
            filed = date.fromisoformat(filing_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("SEC_FILING_DATE_INVALID") from exc
        if not isinstance(form, str) or not form:
            raise ValueError("SEC_FORM_INVALID")
        indexed[accession] = (accepted, form, filed)

    if not isinstance(facts, list):
        raise ValueError("FACTS_MUST_BE_LIST")
    rows = []
    for fact in facts:
        if not isinstance(fact, dict):
            raise ValueError("SEC_FACT_INVALID")
        accession = fact.get("accession", fact.get("accession_number"))
        errors = []
        sec = indexed.get(accession)
        if fact.get("cik") is not None and _cik(fact["cik"]) != issuer:
            errors.append("FACT_CIK_MISMATCH")
        if fact.get("source") not in SEC_FACT_SOURCES:
            errors.append("FACT_NOT_SEC_SOURCED")
        if sec is None:
            errors.append("ACCESSION_NOT_IN_SEC_SOURCE")
        else:
            accepted, form, filed = sec
            if form != fact.get("form_type", fact.get("form")):
                errors.append("SEC_FORM_MISMATCH")
            if filed.isoformat() != fact.get("filing_date"):
                errors.append("SEC_FILING_DATE_MISMATCH")
            if accepted > clock:
                errors.append("SEC_ACCEPTANCE_AFTER_AS_OF")
            for fact_key, reason in (("accepted_at", "FACT_ACCEPTANCE_CONFLICT"),
                                     ("available_at", "FACT_AVAILABLE_BEFORE_SEC_ACCEPTANCE")):
                if fact.get(fact_key):
                    try:
                        fact_clock = _utc(fact[fact_key])
                        if ((fact_key == "accepted_at" and fact_clock != accepted)
                            or (fact_key == "available_at" and fact_clock < accepted)):
                            errors.append(reason)
                        if fact_clock > clock:
                            errors.append("FACT_TIME_AFTER_AS_OF")
                    except ValueError:
                        errors.append("FACT_TIME_INVALID")
        rows.append({
            "accession": accession, "sec_accepted_at": sec[0].isoformat() if sec else None,
            "sec_form": sec[1] if sec else None,
            "sec_filing_date": sec[2].isoformat() if sec else None,
            "join_status": "SEC_ADMINISTRATIVE_CLOCK_MATCH" if not errors else "BLOCKED",
            "reasons": sorted(set(errors)),
            "public_dissemination_at": None,
            "historical_provider_available_at": None,
            "historical_pit_accepted": False,
        })
    return {
        "version": VERSION, "cik": str(issuer).zfill(10),
        "source_sha256": sha256(submissions_raw).hexdigest(),
        "as_of": clock.isoformat(), "source_provenance_independently_verified": False,
        "status": ("SEC_ACCEPTANCE_JOIN_REVIEW_ONLY" if rows and
                   all(r["join_status"] == "SEC_ADMINISTRATIVE_CLOCK_MATCH" for r in rows)
                   else "BLOCKED_MISSING_OR_CONFLICTING_SEC_FACTS"),
        "joins": rows, "public_dissemination_verified": False,
        "historical_provider_available_at_verified": False,
        "historical_pit_accepted": False, "canonical_scores_computed": False,
    }


def _bar(row: dict, as_of: datetime) -> tuple[datetime, float]:
    if not isinstance(row, dict) or not row.get("source") or not row.get("source_ref"):
        raise ValueError("BAR_SOURCE_PROVENANCE_MISSING")
    if not SHA256.fullmatch(str(row.get("evidence_hash", ""))):
        raise ValueError("BAR_SOURCE_HASH_MISSING")
    at = _utc(row.get("timestamp"))
    available = _utc(row.get("available_at"))
    if available < at + timedelta(minutes=1):
        raise ValueError("BAR_AVAILABLE_BEFORE_MINUTE_COMPLETED")
    if at + timedelta(minutes=1) > as_of or available > as_of:
        raise ValueError("BAR_FUTURE_LEAKAGE")
    if at.second or at.microsecond:
        raise ValueError("BAR_NOT_MINUTE_ALIGNED")
    ny = _eastern(at)
    if row.get("exchange_time") and _utc(row["exchange_time"]) != at:
        raise ValueError("BAR_EXCHANGE_CLOCK_MISMATCH")
    if row.get("session"):
        minute = ny.hour * 60 + ny.minute
        expected = ("PREMARKET_CLOCK" if 240 <= minute < 570
                    else "REGULAR_CLOCK" if 570 <= minute < 960 else "OTHER_CLOCK")
        if row["session"] != expected:
            raise ValueError("BAR_SESSION_CLOCK_MISMATCH")
    try:
        volume = float(row["volume"])
    except (ValueError, TypeError, KeyError) as exc:
        raise ValueError("BAR_VOLUME_INVALID") from exc
    if not math.isfinite(volume) or volume < 0:
        raise ValueError("BAR_VOLUME_INVALID")
    return at, volume


def _publication(event: dict, as_of: datetime) -> None:
    if not isinstance(event, dict) or not event.get("source") or not event.get("source_ref"):
        raise ValueError("NEWS_SOURCE_PROVENANCE_MISSING")
    if not SHA256.fullmatch(str(event.get("evidence_hash", ""))):
        raise ValueError("NEWS_SOURCE_HASH_MISSING")
    first = _utc(event.get("first_published_at"))
    received = _utc(event.get("available_at"))
    if first > received or received > as_of:
        raise ValueError("NEWS_PUBLISHED_AVAILABLE_CLOCK_INVALID")
    if event.get("first_publication_independently_verified") is not True:
        raise ValueError("NEWS_FIRST_PUBLICATION_UNVERIFIED")
    local = _eastern(first)
    if local.date() != _eastern(as_of).date() or not 560 <= local.hour*60 + local.minute <= 600:
        raise ValueError("NEWS_OUTSIDE_0920_1000_ET")


def audit_s16ea_session_evidence(
    current_bars: list[dict], historical_bars: list[dict], news_events: list[dict], *,
    route: str, evaluated_at: str | datetime, calendar_evidence: dict | None = None,
    min_same_clock_sessions: int = 20,
) -> dict:
    """Review closed-minute as-of access, same ET clock and source sessions.

    A median is an uncalibrated diagnostic, never a frozen S16-EA percentile.
    Even perfect caller-supplied evidence is only a review candidate until an
    independent source/calendar provenance audit is performed.
    """
    clock = _utc(evaluated_at)
    if route not in ROUTES or not isinstance(min_same_clock_sessions, int) or not 2 <= min_same_clock_sessions <= 100:
        raise ValueError("INVALID_ROUTE_OR_BASELINE_REQUIREMENT")
    if not all(isinstance(x, list) for x in (current_bars, historical_bars, news_events)):
        raise ValueError("EVENT_EVIDENCE_LISTS_REQUIRED")
    ny_clock = _eastern(clock)
    target = clock.replace(second=0, microsecond=0) - timedelta(minutes=1)
    target_ny = _eastern(target)
    target_date = ny_clock.date()
    target_minute = target_ny.hour * 60 + target_ny.minute
    errors = []
    if target_ny.date() != target_date:
        errors.append("NO_COMPLETE_MINUTE_IN_EVALUATION_SESSION")
    window_start, window_end = ((560, 600) if route == "NEWS_AT_OPEN" else (571, 584))
    eval_minute = ny_clock.hour * 60 + ny_clock.minute
    if not window_start <= eval_minute <= window_end:
        errors.append("OUTSIDE_S16EA_ROUTE_WINDOW_ET")

    calendar_days = set()
    if not isinstance(calendar_evidence, dict) or not calendar_evidence.get("source_ref") or not SHA256.fullmatch(str(calendar_evidence.get("source_sha256", ""))):
        errors.append("EXCHANGE_SESSION_CALENDAR_EVIDENCE_MISSING")
    else:
        try:
            calendar_days = {date.fromisoformat(day) for day in calendar_evidence["session_dates"]}
            if not calendar_days or len(calendar_days) != len(calendar_evidence["session_dates"]):
                errors.append("EXCHANGE_SESSION_CALENDAR_INVALID")
        except (KeyError, ValueError, TypeError):
            errors.append("EXCHANGE_SESSION_CALENDAR_INVALID")
    if target_date not in calendar_days:
        errors.append("EVALUATION_DATE_NOT_IN_SOURCE_SESSION_CALENDAR")

    current = {}
    for row in current_bars:
        try:
            at, volume = _bar(row, clock)
            if _eastern(at).date() != target_date:
                raise ValueError("CURRENT_BAR_OUTSIDE_EVALUATION_DATE")
            if at in current:
                raise ValueError("DUPLICATE_CURRENT_MINUTE")
            current[at] = volume
        except ValueError as exc:
            errors.append(str(exc))
    if target not in current:
        errors.append("EVALUATION_CLOSED_MINUTE_MISSING")
    if route == "ZERO_PM_BREAKOUT":
        # Missing premarket bars cannot establish a quiet or zero-volume PM.
        if not any(240 <= _eastern(t).hour*60 + _eastern(t).minute < 570 for t in current):
            errors.append("PREMARKET_OBSERVATIONS_MISSING")
        for minute in range(570, max(570, target_minute + 1)):
            wall = ny_clock.replace(hour=minute//60, minute=minute%60, second=0, microsecond=0)
            if wall.astimezone(timezone.utc) not in current:
                errors.append("REGULAR_MINUTE_SEQUENCE_INCOMPLETE")
                break

    same_clock = {}
    for row in historical_bars:
        try:
            at, volume = _bar(row, clock)
            wall = _eastern(at)
            if wall.date() >= target_date or wall.date() not in calendar_days:
                raise ValueError("HISTORICAL_BAR_DATE_NOT_VERIFIED_SESSION")
            if wall.hour*60 + wall.minute != target_minute:
                continue
            if wall.date() in same_clock:
                raise ValueError("DUPLICATE_HISTORICAL_SAME_CLOCK_SESSION")
            same_clock[wall.date()] = volume
        except ValueError as exc:
            errors.append(str(exc))
    if len(same_clock) < min_same_clock_sessions:
        errors.append("SAME_CLOCK_HISTORY_INSUFFICIENT")

    if route == "NEWS_AT_OPEN":
        if not news_events:
            errors.append("NEWS_FIRST_PUBLICATION_EVIDENCE_MISSING")
        for event in news_events:
            try:
                _publication(event, clock)
            except ValueError as exc:
                errors.append(str(exc))

    return {
        "version": VERSION, "route": route, "evaluated_at": clock.isoformat(),
        "exchange_clock": ny_clock.isoformat(),
        "baseline_et_minute": f"{target_minute//60:02d}:{target_minute%60:02d}",
        "status": ("RESEARCH_CLOCK_CANDIDATE_REVIEW_ONLY" if not errors
                   else "BLOCKED_MISSING_OR_INVALID_EVIDENCE"),
        "reasons": sorted(set(errors)),
        "same_clock_sessions": len(same_clock),
        "required_same_clock_sessions_research_threshold": min_same_clock_sessions,
        "same_clock_median_volume_diagnostic": (median(same_clock.values())
            if not errors and len(same_clock) >= min_same_clock_sessions else None),
        "calendar_provenance_independently_verified": False,
        "eastern_timezone_source": ("IANA_ZONEINFO" if NY is not None
                                     else "BOUNDED_US_DST_RULE_2024_2026_CLOCK_CANDIDATE"),
        "news_first_publication_independently_reverified": False,
        "historical_pit_accepted": False,
        "score": None, "verified_alarm": False, "notification_sent": False,
    }
