"""Unapproved S16-E proposal: pure offline experiments, never a runtime model.

All numbers are NEW design proposals, not recovered S16-C/EA contracts.
Caller attestation is not independent evidence authentication or PIT acceptance.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
import re
from typing import Mapping, Sequence

VERSION = "S16-E-EXPERIMENT-DRAFT-0.2"
ACTIVATION_STATUS = "PENDING_APPROVAL"


@dataclass(frozen=True)
class Factor:
    key: str
    unit: str
    low: float
    high: float
    weight: float
    minimum: float
    maximum: float
    max_age_hours: float
    reverse: bool = False


# Clamp linear transforms to [0,100]. Weights sum to one; no missing renormalization.
FACTORS = (
    Factor("return_5_sessions", "fraction", -.10, .20, .20, -1, 100, 96),
    Factor("rvol_20_sessions", "ratio", .5, 3, .20, 0, 1000, 96),
    Factor("mean_dollar_volume_20_sessions", "USD", 1e6, 20e6, .15, 0, 1e14, 96),
    Factor("public_float_shares", "shares", 5e6, 200e6, .10, 1, 1e13, 24*100, True),
    Factor("catalyst_age_hours", "hours", 0, 120, .15, 0, 120, 120, True),
    Factor("fcf_margin_ttm", "fraction", -.10, .30, .10, -100, 100, 24*180),
    Factor("benchmark_return_20_sessions", "fraction", -.10, .10, .10, -1, 100, 96),
)
# Penalties: nonnegative linear proposals, cap 15 points each.
RISKS = (
    Factor("dilution_yoy", "fraction", .02, .20, 15, -1, 100, 24*180),
    Factor("quoted_spread_bps", "bps", 20, 200, 15, 0, 1e5, 1),
    Factor("realized_volatility_20_sessions", "annualized_fraction", .40, 1.20, 15, 0, 100, 96),
)


@dataclass(frozen=True)
class Evidence:
    value: float
    unit: str
    period_end: datetime
    available_at: datetime
    observed_at: datetime
    source_ref: str
    sha256: str
    # Must be independently archived provider/capture timing, not SEC Accepted.
    availability_basis: str
    identity_confirmed: bool


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timezone-aware timestamp required")
    return value.astimezone(timezone.utc)


def _finite(value: float) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def _normalized(value: float, spec: Factor) -> float:
    score = min(100.0, max(0.0, 100 * (value-spec.low)/(spec.high-spec.low)))
    return 100-score if spec.reverse else score


def experiment(
    evidence: Mapping[str, Evidence], *, as_of: datetime,
    acknowledge_unapproved_experiment: bool = False,
) -> dict:
    """Compute only when explicitly requested; always returns canonical=False.

    All ten factors/risks are required. Temporal checks intentionally reject
    retrospective observations. Hash/source strings are only metadata checks;
    independent verification of their bytes and metric definitions is external.
    """
    result = dict(version=VERSION, activation_status=ACTIVATION_STATUS,
                  canonical=False, runtime_enabled=False, confidence="UNCALIBRATED",
                  experimental_score=None, normalized={}, penalties={}, issues=[])
    if acknowledge_unapproved_experiment is not True:
        return dict(result, status="EXPERIMENT_NOT_REQUESTED")
    decision = _utc(as_of)
    issues = []
    expected = {s.key for s in FACTORS + RISKS}
    if set(evidence)-expected:
        issues.append("UNKNOWN_FACTORS")
    for spec in FACTORS + RISKS:
        item = evidence.get(spec.key)
        if not isinstance(item, Evidence):
            issues.append(f"{spec.key}:MISSING")
            continue
        if not _finite(item.value) or not spec.minimum <= item.value <= spec.maximum:
            issues.append(f"{spec.key}:INVALID_VALUE")
        if item.unit != spec.unit:
            issues.append(f"{spec.key}:UNIT_MISMATCH")
        if (item.identity_confirmed is not True or
            not isinstance(item.source_ref, str) or not item.source_ref.startswith("https://") or
            not isinstance(item.sha256, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", item.sha256) or
            item.availability_basis != "PROVIDER_CAPTURE_LOG"):
            issues.append(f"{spec.key}:UNVERIFIED_PROVENANCE")
        try:
            period, available, observed = map(_utc, (item.period_end, item.available_at, item.observed_at))
        except ValueError:
            issues.append(f"{spec.key}:INVALID_TIME")
            continue
        if not period <= available <= observed <= decision:
            issues.append(f"{spec.key}:TIME_LEAK_OR_ORDER")
        if (decision-period).total_seconds()/3600 > spec.max_age_hours:
            issues.append(f"{spec.key}:STALE")
        if spec.key == "catalyst_age_hours" and _finite(item.value):
            # period_end is the independently evidenced first public event time.
            if not math.isclose(item.value, (decision-period).total_seconds()/3600, abs_tol=1/3600):
                issues.append(f"{spec.key}:AGE_MISMATCH")
    result["issues"] = issues
    result["coverage"] = {"present": sum(isinstance(evidence.get(s.key), Evidence) for s in FACTORS+RISKS),
                          "required": len(FACTORS+RISKS)}
    if issues:
        return dict(result, status="NO_SCORE")
    normalized = {s.key: _normalized(evidence[s.key].value, s) for s in FACTORS}
    penalties = {s.key: _normalized(evidence[s.key].value, s)*s.weight/100 for s in RISKS}
    total = sum(normalized[s.key]*s.weight for s in FACTORS) - sum(penalties.values())
    return dict(result, status="EXPERIMENT_ONLY", experimental_score=round(max(0., min(100., total)), 6),
                normalized=normalized, penalties=penalties)


@dataclass(frozen=True)
class ReplayCase:
    case_id: str
    decision_at: datetime
    evidence: Mapping[str, Evidence]
    outcome_end: datetime
    label_available_at: datetime
    outcome_return: float


def evaluate_frozen_replay(
    cases: Sequence[ReplayCase], *, evaluation_as_of: datetime, alert_threshold: float,
    positive_return_threshold: float, acknowledge_unapproved_experiment: bool = False,
) -> dict:
    """Evaluate predeclared thresholds; never fit weights or choose a threshold.

    Caller must supply a separately audited 1-5-session outcome, corporate action
    and delisting treatment. This mechanical harness cannot certify that evidence.
    No statistical confidence interval or real-world skill is inferred.
    """
    if acknowledge_unapproved_experiment is not True:
        raise ValueError("Explicit offline experiment acknowledgement required")
    if not _finite(alert_threshold) or not 0 <= alert_threshold <= 100:
        raise ValueError("Invalid alert threshold")
    if not _finite(positive_return_threshold):
        raise ValueError("Invalid outcome threshold")
    cutoff = _utc(evaluation_as_of)
    if len({case.case_id for case in cases}) != len(cases):
        raise ValueError("Duplicate replay cases")
    counts = dict(tp=0, fp=0, tn=0, fn=0)
    excluded = []
    for case in cases:
        decision, end, label_time = map(_utc, (case.decision_at, case.outcome_end, case.label_available_at))
        if not decision < end <= label_time <= cutoff or not _finite(case.outcome_return):
            excluded.append({"case_id": case.case_id, "reason": "UNMATURED_OR_INVALID_LABEL"})
            continue
        score = experiment(case.evidence, as_of=decision, acknowledge_unapproved_experiment=True)
        if score["status"] != "EXPERIMENT_ONLY":
            excluded.append({"case_id": case.case_id, "reason": "INVALID_ASOF_FEATURES"})
            continue
        alert = score["experimental_score"] >= alert_threshold
        positive = case.outcome_return >= positive_return_threshold
        counts[("t" if alert == positive else "f") + ("p" if alert else "n")] += 1
    alerts = counts["tp"] + counts["fp"]
    negatives = counts["tn"] + counts["fp"]
    return dict(version=VERSION, activation_status=ACTIVATION_STATUS, canonical=False,
                confidence="UNCALIBRATED", counts=counts, excluded=excluded,
                precision=counts["tp"]/alerts if alerts else None,
                false_positive_rate=counts["fp"]/negatives if negatives else None,
                false_alert_fraction=counts["fp"]/alerts if alerts else None,
                threshold_selection="EXTERNAL_PREDECLARED_NOT_FITTED",
                cohort_and_outcomes_status="EXTERNAL_AUDIT_REQUIRED")
