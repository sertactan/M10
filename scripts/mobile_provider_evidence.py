"""Research-only provider normalization and S16 input coverage inventory.

NOT a unified live feed, official pricing, historical PIT certification,
estimated model implementation, or canonical scoring engine. No I/O, trades,
API credentials, source substitutions or canonical model edits.
"""
from __future__ import annotations

from dataclasses import fields
from datetime import datetime, timezone
from math import isfinite
from core.models.s16_contracts import S16Input

SCHEMA = "MERIDYEN_MOBILE_PROVIDER_EVIDENCE_V1"
SIGNALS = tuple(
    f.name for f in fields(S16Input)
    if f.name not in {"security_id", "ticker", "as_of", "route"}
)
RISK_FIELDS = {"dilution_risk", "extension_risk", "data_risk",
               "liquidity_risk", "manipulation_risk"}


def instant(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("missing UTC/offset-aware timestamp")
    date = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if date.tzinfo is None or date.utcoffset() is None:
        raise ValueError("timezone missing")
    return date.astimezone(timezone.utc)


def normalize_daily_quote(data, provider):
    """Strictly label a DAILY price observation and preserve provenance."""
    if provider not in {"YFINANCE_YAHOO_UNOFFICIAL", "OPENBB_FREE"}:
        raise ValueError("unknown provider")
    if not isinstance(data, dict):
        raise ValueError("missing provider payload")
    ticker = data.get("symbol", "")
    if not isinstance(ticker, str) or not ticker:
        raise ValueError("missing ticker")
    ticker = ticker.upper().strip()
    if provider == "YFINANCE_YAHOO_UNOFFICIAL":
        if data.get("status") != "OK_UNOFFICIAL_DAILY_BAR":
            raise ValueError("upstream quote not verified")
        price = data.get("price")
        date = data.get("bar_date")
        retrieval = data.get("retrieved_at_utc")
        source = data.get("source")
        if source != provider:
            raise ValueError("wrong source identity")
    else:
        if data.get("status") != "UPSTREAM_FETCH_VERIFIED":
            raise ValueError("OpenBB historical fetch not verified")
        bars = data.get("bars") or []
        if not isinstance(bars, list) or not bars:
            raise ValueError("no OpenBB price bars")
        # OpenBB can return bars in ascending or descending date order.
        if any(not isinstance(row, dict) or not isinstance(row.get("date"), str)
               for row in bars):
            raise ValueError("bar source dates unavailable")
        last = max(bars, key=lambda row: row["date"][:10])
        price = last.get("close")
        date = last.get("date")
        retrieval = data.get("retrieved_at")
        source = data.get("provider", "")
        if source not in {"openbb.cboe", "openbb.nasdaq"}:
            raise ValueError("OpenBB provider not verified")
    try:
        numeric = float(price)
    except (TypeError, ValueError):
        raise ValueError("price missing or invalid")
    if not isfinite(numeric) or numeric <= 0:
        raise ValueError("price must be positive and finite")
    collected = instant(retrieval)
    # An exchange's daily timestamp may have an explicit intraday clock, but
    # it must never be later than observed retrieval time.
    if not isinstance(date, str) or len(date) < 10:
        raise ValueError("daily bar timestamp missing")
    raw_date = date[:10]
    try:
        from datetime import date as dt_date
        parsed = dt_date.fromisoformat(raw_date)
    except ValueError:
        raise ValueError("invalid trading-bar date")
    if parsed > collected.date():
        raise ValueError("bar date ahead of retrieval date")
    return {
        "schema": SCHEMA, "ticker": ticker, "daily_close": numeric,
        "bar_date": raw_date, "retrieved_at_utc": collected.isoformat(),
        "provider": source, "currency": "USD_UNVERIFIED",
        "adjustment": "UNKNOWN", "intraday": False, "real_time_verified": False,
        "pit_valid": False, "canonical_eligible": False,
        "s16_e": "NOT_COMPUTED", "s16_c": "INCONCLUSIVE_MISSING_PIT",
        "note": "Research-only quote, delayed/market-adjustment unknown.",
    }


def compare_daily_prices(left, right):
    """Only compare aligned dates; unknown currency is explicitly unverified."""
    if left.get("ticker") != right.get("ticker"):
        return {"status": "BLOCKED_TICKER_MISMATCH"}
    if left.get("bar_date") != right.get("bar_date"):
        return {"status": "BLOCKED_DATE_MISMATCH"}
    if left.get("currency") != right.get("currency"):
        return {"status": "BLOCKED_CURRENCY_UNVERIFIED_OR_MISMATCH"}
    if left.get("currency") == "USD_UNVERIFIED":
        return {"status": "BLOCKED_CURRENCY_UNVERIFIED"}
    if left.get("adjustment") != right.get("adjustment") or left.get("adjustment") == "UNKNOWN":
        return {"status": "BLOCKED_ADJUSTMENT_UNVERIFIED"}
    raise ValueError("numeric comparison unavailable until fully certified source contracts exist")


def inventory_s16_evidence(ticker, as_of, evidence):
    """Inventory 22 model inputs without substituting missing fields as zero."""
    bound = instant(as_of)
    if not isinstance(ticker, str) or not ticker.strip():
        raise ValueError("ticker required")
    if not isinstance(evidence, dict):
        raise ValueError("evidence must be a dict")
    missing = sorted(set(SIGNALS) - set(evidence))
    malformed, future, source_gaps, non_pit = [], [], [], []
    for name in SIGNALS:
        if name not in evidence:
            continue
        entry = evidence[name]
        if not isinstance(entry, dict):
            malformed.append(name)
            continue
        try:
            value = float(entry["value"])
            if not isfinite(value) or not (0 <= value <= (1 if name in RISK_FIELDS else 100)):
                malformed.append(name)
        except (ValueError, TypeError, KeyError):
            malformed.append(name)
        if not entry.get("source") or not entry.get("source_ref"):
            source_gaps.append(name)
        try:
            observed, available = instant(entry.get("observed_at")), instant(entry.get("available_at"))
            if available < observed or observed > bound or available > bound:
                future.append(name)
        except (ValueError, TypeError):
            future.append(name)
        if entry.get("pit_verified") is not True:
            non_pit.append(name)
    blockers = []
    if missing: blockers.append("MISSING_S16_COMPONENTS")
    if malformed: blockers.append("INVALID_S16_COMPONENT_VALUES")
    if future: blockers.append("TIME_LEAKAGE_OR_INVALID_VINTAGE")
    if source_gaps: blockers.append("SOURCE_EVIDENCE_MISSING")
    if non_pit: blockers.append("PIT_ATTESTATION_MISSING")
    return {
        "schema": SCHEMA, "ticker": ticker.upper(), "as_of": bound.isoformat(),
        "required_count": len(SIGNALS), "submitted_count": len(SIGNALS)-len(missing),
        "missing": missing, "invalid_values": sorted(set(malformed)),
        "future_or_invalid_dates": sorted(set(future)),
        "missing_source": sorted(set(source_gaps)), "unverified_pit": sorted(set(non_pit)),
        "status": "BLOCKED_INPUT_GATES" if blockers else "SOURCE_ASSERTED_READY_NEEDS_INDEPENDENT_AUDIT",
        "blockers": blockers, "canonical_certified": False,
        "s16_e": "NOT_COMPUTED", "s16_c": "INCONCLUSIVE_NEEDS_INDEPENDENT_AUDIT",
        "score_calculated": False,
        "note": "Source-provided PIT attestations are not independent validation. Frozen S16 weights/gates never called.",
    }


def normalize_social_scan(data):
    """Inventory one-shot Social V5 source coverage, NEVER model sentiment/S16."""
    if not isinstance(data, dict) or data.get("module") != "MERIDYEN_SOCIAL_V5_FREE":
        raise ValueError("not an authenticated/declared Social V5 response")
    ticker = data.get("ticker")
    if not isinstance(ticker, str) or not ticker:
        raise ValueError("ticker missing")
    posts = data.get("posts")
    if not isinstance(posts, list):
        raise ValueError("posts list missing")
    for item in posts:
        if not isinstance(item, dict) or not item.get("source_url"):
            raise ValueError("social source provenance missing")
        try:
            observed = instant(item.get("observed_at"))
            created = instant(item.get("created_at"))
            if observed < created:
                raise ValueError("social post observed before publication")
        except (ValueError, TypeError) as exc:
            raise ValueError("social post invalid timestamp") from exc
    return {
        "schema": SCHEMA, "ticker": ticker.upper(),
        "provider": "MERIDYEN_SOCIAL_V5_FREE", "one_shot_posts": len(posts),
        "source_status": data.get("source_status"),
        "historical_baseline_verified": False,
        "cross_platform_market_coverage_verified": False,
        "pit_valid": False, "canonical_eligible": False,
        "s16_e": "NOT_COMPUTED", "s16_c": "INCONCLUSIVE_MISSING_PIT",
        "note": "One-shot public posts never establish full social velocity baseline.",
    }
