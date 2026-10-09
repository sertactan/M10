from dataclasses import replace
from datetime import datetime, timedelta, timezone

from core.runtime.strict_free import FreeLLMEvidence, authorize_free_llm


NOW = datetime(2026, 10, 10, tzinfo=timezone.utc)


def _verified():
    return FreeLLMEvidence(
        provider="TEST_PROVIDER", model_id="free-model-id", verified_at=NOW,
        free_tier_confirmed=True, billing_disabled_or_hard_capped=True,
        remaining_free_requests=3, internal_requests_remaining=2,
    )


def test_missing_and_unverified_fail_closed():
    assert authorize_free_llm(None, now=NOW).reason == "MISSING_PROVIDER_EVIDENCE"
    assert not authorize_free_llm(replace(_verified(), free_tier_confirmed=False), now=NOW).allowed
    assert not authorize_free_llm(replace(_verified(), billing_disabled_or_hard_capped=False), now=NOW).allowed


def test_no_quota_and_stale_evidence_fail_closed():
    assert not authorize_free_llm(replace(_verified(), remaining_free_requests=0), now=NOW).allowed
    assert not authorize_free_llm(replace(_verified(), internal_requests_remaining=0), now=NOW).allowed
    assert not authorize_free_llm(replace(_verified(), verified_at=NOW-timedelta(days=2)), now=NOW).allowed
    assert not authorize_free_llm(replace(_verified(), verified_at=NOW+timedelta(hours=1)), now=NOW).allowed


def test_verified_request_preflight_allowed():
    result = authorize_free_llm(_verified(), now=NOW)
    assert result.allowed and result.reason == "FREE_REQUEST_PREFLIGHT_ALLOWED"


def test_naive_timestamp_and_missing_identity_blocked():
    assert not authorize_free_llm(replace(_verified(), verified_at=NOW.replace(tzinfo=None)), now=NOW).allowed
    assert not authorize_free_llm(replace(_verified(), model_id="  "), now=NOW).allowed
