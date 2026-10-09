"""Fail-closed permission gate for optional FREE LLM requests.

This is a preflight policy, not a guarantee against provider billing or an
HTTP client. No API requests are made by this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class FreeLLMEvidence:
    provider: str
    model_id: str
    verified_at: datetime
    free_tier_confirmed: bool
    billing_disabled_or_hard_capped: bool
    remaining_free_requests: int
    internal_requests_remaining: int


@dataclass(frozen=True)
class GateDecision:
    allowed: bool
    reason: str


def authorize_free_llm(
    evidence: FreeLLMEvidence | None,
    *,
    now: datetime | None = None,
    max_evidence_age: timedelta = timedelta(hours=24),
) -> GateDecision:
    """Permit only verified, strictly no-billable model requests.

    The caller MUST atomically reserve both quotas before sending the request.
    If the remote provider cannot guarantee hard spend limits, keep blocked.
    """
    if evidence is None:
        return GateDecision(False, "MISSING_PROVIDER_EVIDENCE")
    current = now if now is not None else datetime.now(timezone.utc)
    if current.tzinfo is None or evidence.verified_at.tzinfo is None:
        return GateDecision(False, "INVALID_TIMESTAMP")
    if not evidence.provider.strip() or not evidence.model_id.strip():
        return GateDecision(False, "MISSING_MODEL_IDENTITY")
    age = current - evidence.verified_at
    if max_evidence_age <= timedelta(0) or age < timedelta(0) or age > max_evidence_age:
        return GateDecision(False, "EVIDENCE_STALE_OR_FUTURE")
    if not evidence.free_tier_confirmed:
        return GateDecision(False, "FREE_TIER_NOT_VERIFIED")
    if not evidence.billing_disabled_or_hard_capped:
        return GateDecision(False, "BILLING_NOT_HARD_BLOCKED")
    if evidence.remaining_free_requests <= 0 or evidence.internal_requests_remaining <= 0:
        return GateDecision(False, "FREE_QUOTA_EXHAUSTED")
    return GateDecision(True, "FREE_REQUEST_PREFLIGHT_ALLOWED")
