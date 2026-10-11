"""Fail-closed S16-E OOS cohort and leakage audit; no score calculation."""
from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha256
import json

from app.scoring_estimated_draft import ACTIVATION_STATUS, FACTORS, RISKS


REQUIRED_FACTORS = frozenset(spec.key for spec in FACTORS + RISKS)
SPLITS = {
    "TRAIN": (date(2024, 1, 2), date(2024, 12, 31)),
    "VALIDATION": (date(2025, 1, 1), date(2025, 4, 30)),
    "HOLDOUT": (date(2025, 5, 1), date(2025, 9, 30)),
}


def _clock(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("TIMESTAMP_STRING_REQUIRED")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("TIMESTAMP_INVALID") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("OFFSET_AWARE_TIMESTAMP_REQUIRED")
    return parsed.astimezone(timezone.utc)


def check_case(case: dict, *, evaluation_as_of: str) -> list[str]:
    """Check a sourced case without scoring or fitting its proposed factors."""
    issues = []
    split = case.get("split")
    if split not in SPLITS:
        return ["SPLIT_NOT_PREDECLARED"]
    try:
        decision = _clock(case["decision_at"])
        outcome_end = _clock(case["outcome_end"])
        label_at = _clock(case["label_available_at"])
    except (KeyError, ValueError):
        return ["CASE_CLOCKS_MISSING_OR_INVALID"]
    cutoff = _clock(evaluation_as_of)
    start, end = SPLITS[split]
    if not start <= decision.date() <= end:
        issues.append("DECISION_OUTSIDE_SPLIT")
    if not decision < outcome_end <= label_at <= cutoff:
        issues.append("FUTURE_OR_UNMATURED_LABEL")
    next_start = SPLITS["VALIDATION"][0] if split == "TRAIN" else SPLITS["HOLDOUT"][0] if split == "VALIDATION" else None
    if next_start and label_at.date() >= next_start:
        issues.append("LABEL_CROSSES_NEXT_SPLIT")
    if case.get("verified_exchange_session_horizon") is not True:
        issues.append("FIVE_SESSION_HORIZON_UNVERIFIED")
    for key in ("historical_identity_verified", "corporate_actions_verified",
                "delisting_outcome_verified", "contemporaneous_membership_verified"):
        if case.get(key) is not True:
            issues.append(key.upper() + "_MISSING")
    factors = case.get("factors")
    if not isinstance(factors, dict) or set(factors) != REQUIRED_FACTORS:
        issues.append("TEN_REQUIRED_FACTORS_MISSING")
    else:
        for key in REQUIRED_FACTORS:
            evidence = factors[key]
            if (not isinstance(evidence, dict) or not evidence.get("source_ref")
                    or not evidence.get("source_sha256")
                    or evidence.get("availability_basis") != "HISTORICAL_PROVIDER_CAPTURE"):
                issues.append(key + ":PROVENANCE_MISSING")
                continue
            try:
                if _clock(evidence["first_available_at"]) > decision:
                    issues.append(key + ":LOOKAHEAD")
            except (KeyError, ValueError):
                issues.append(key + ":FIRST_AVAILABLE_CLOCK_MISSING")
    return sorted(set(issues))


def audit_real_pilot(raw: bytes, *, evaluation_as_of: str) -> dict:
    """Inventory the real Phase25W pilot; do not infer absent case-level data."""
    source = json.loads(raw)
    if source.get("schema") is None or source.get("canonical_accepted_securities_proven") != 0:
        raise ValueError("UNEXPECTED_PILOT_STATUS")
    candidates = source.get("pilot_candidates")
    if not isinstance(candidates, list) or len(candidates) != 25:
        raise ValueError("PILOT_COHORT_NOT_25")
    ids = [str(row["simfin_id"]) for row in candidates]
    if len(set(ids)) != len(ids):
        raise ValueError("DUPLICATE_PILOT_SECURITY_ID")
    dates = []
    for row in candidates:
        first, last = date.fromisoformat(row["first_source_price_date"]), date.fromisoformat(row["last_source_price_date"])
        if first > last or row.get("source_price_rows", 0) <= 0:
            raise ValueError("PILOT_PRICE_RANGE_INVALID")
        dates.extend((first, last))
    # A dated price range is not a provider-captured factor/case observation.
    missing = [
        "TEN_FACTOR_HISTORICAL_PROVIDER_CAPTURE_ENVELOPES",
        "FIRST_PUBLIC_CATALYST_EVENT_TIMES",
        "CONTEMPORANEOUS_BID_ASK_SPREAD",
        "HISTORICAL_PUBLIC_FLOAT_AND_DILUTION",
        "CORPORATE_ACTION_AND_DELISTING_OUTCOME_CHAIN",
        "CONTEMPORANEOUS_MEMBERSHIP_AND_SECURITY_IDENTITY",
        "EXCHANGE_SESSION_CALENDAR_AND_FIVE_SESSION_LABELS",
        "CASE_LEVEL_DECISION_OUTCOME_AND_LABEL_TIMESTAMPS",
        "PREDECLARED_THRESHOLD_AND_UNTOUCHED_HOLDOUT_APPROVAL",
    ]
    return {"schema": "M10_V13_S16E_OOS_READINESS_V1",
            "source_sha256": sha256(raw).hexdigest(),
            "source_schema": source["schema"],
            "pilot_security_count": len(candidates),
            "observed_source_price_range": {"first": min(dates).isoformat(), "last": max(dates).isoformat()},
            "proposed_splits": {name: [a.isoformat(), b.isoformat()] for name, (a, b) in SPLITS.items()},
            "required_factor_keys": sorted(REQUIRED_FACTORS),
            "case_level_rows_with_10_independently_captured_factors": 0,
            "eligible_oos_cases": 0,
            "metrics": None,
            "missing": missing,
            "source_global_blockers": source.get("remaining_global_blockers", []),
            "activation_status": ACTIVATION_STATUS,
            "runtime_enabled": False,
            "canonical": False,
            "evaluation_as_of": _clock(evaluation_as_of).isoformat()}
