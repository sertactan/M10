from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from core.hermes_team.adapters import plugin_response, telegram_message
from core.hermes_team.contracts import financial_result
from core.hermes_team.gateway import check_payload, perform
from core.hermes_team.guard import Blocked, Policy, QuotaGuard
from core.hermes_team.m10_bridge import canonical_s16_from_verified_features
from core.hermes_team.roles import ROLES, route


def policy():
    return Policy(enabled=True, provider="openrouter", model="test/model:free",
                  free_tier_verified=True, nonbillable_account_verified=True,
                  verification_expires_epoch=4102444800, daily_request_cap=2,
                  minute_request_cap=2)


def payload():
    return {"model": "test/model:free", "messages": [{"role": "user", "content": "test"}],
            "max_tokens": 32}


def test_six_roles():
    assert len(ROLES) == 6
    assert route("risk", allow_llm=True)["execution"] == "PYTHON_OR_REVIEW"
    assert route("catalyst", allow_llm=True)["execution"] == "LLM_GATEWAY"
    assert route("unknown")["status"] == "INCONCLUSIVE"


def test_free_gateway_rejects_model_override_tools_stream():
    for change in ({"model": "paid"}, {"tools": []}, {"stream": True},
                   {"max_tokens": 999999}, {"messages": [{"role": "user", "content": ["image"]}]}):
        with pytest.raises(Blocked):
            check_payload({**payload(), **change}, policy())


def test_guard_rejects_unverified_and_nonfree(tmp_path):
    guard = QuotaGuard(tmp_path / "quota.sqlite3")
    for p in (replace(policy(), enabled=False),
              replace(policy(), nonbillable_account_verified=False),
              replace(policy(), model="paid/model"),
              replace(policy(), verification_expires_epoch=1)):
        with pytest.raises(Blocked):
            guard.reserve(request_id="x", policy=p, prompt_bytes=20, now=2000000000)


def test_guard_one_at_time_quota_and_duplicate(tmp_path):
    guard = QuotaGuard(tmp_path / "quota.sqlite3")
    p = policy()
    when = 2000000000
    guard.reserve(request_id="first", policy=p, prompt_bytes=20, now=when)
    with pytest.raises(Blocked, match="ONE_LLM"):
        guard.reserve(request_id="second", policy=p, prompt_bytes=20, now=when)
    guard.finish("first")
    with pytest.raises(Blocked, match="DUPLICATE"):
        guard.reserve(request_id="first", policy=p, prompt_bytes=20, now=when)
    guard.reserve(request_id="second", policy=p, prompt_bytes=20, now=when)
    guard.finish("second")
    with pytest.raises(Blocked, match="QUOTA"):
        guard.reserve(request_id="third", policy=p, prompt_bytes=20, now=when)


def test_no_network_mocked_remote_call(tmp_path):
    guard = QuotaGuard(tmp_path / "quota.sqlite3")
    calls = []

    def transport(p, data):
        calls.append((p.model, json.loads(data)["max_tokens"]))
        return b'{"choices":[{"message":{"role":"assistant","content":"research only"}}]}'

    result = perform(payload(), policy=policy(), guard=guard, transport=transport)
    assert result["choices"][0]["message"]["content"] == "research only"
    assert calls == [("test/model:free", 32)]


def test_financial_evidence_gate_and_separate_scores():
    incomplete = financial_result({"symbol": "INOD", "s16_c": 92, "s16_e": 67})
    assert incomplete["s16_c"] is None and incomplete["decision"] == "INCONCLUSIVE"
    trusted = financial_result({
        "symbol": "INOD", "price": 8.5, "price_timestamp": "2026-10-09T16:00:00Z",
        "sources": [{"source": "SEC", "source_ref": "filing", "retrieved_at": "2026-10-09",
                     "available_at": "2026-10-09"}],
        "s16_e": 61, "s16_c": 83, "canonical_evidence_verified": True
    })
    assert trusted["s16_e"] is None and trusted["s16_c"] is None
    assert trusted["s16_e_status"] == "INCONCLUSIVE"
    assert "S16-E: N/A" in telegram_message(trusted)
    assert financial_result({
        "symbol": "INOD", "price": 8.5, "price_timestamp": "2026-10-09T16:00:00Z",
        "sources": [{"source": "SEC", "source_ref": "filing",
                     "retrieved_at": "2026-10-09", "available_at": "2026-10-09"}],
        "s16_e": 61,
    }, estimated_trusted=True)["s16_e_status"] == "ESTIMATED"
    assert "S16-C: INCONCLUSIVE" in telegram_message(trusted)
    assert plugin_response(trusted)["transport_connected"] is False


def test_bridge_denies_llm_invented_s16():
    report = canonical_s16_from_verified_features({
        "symbol": "INOD", "s16_c": 99, "canonical_evidence_verified": True,
        "feature_origin": "LLM"
    })
    assert report["s16_c"] is None and report["s16_c_status"] == "INCONCLUSIVE"


def test_scores_refuse_nonfinite_or_untrusted_values():
    raw = {"symbol": "INOD", "price": 8.5, "price_timestamp": "2026-10-09T16:00:00Z",
           "sources": [{"source": "SEC", "source_ref": "filing",
                        "retrieved_at": "2026-10-09", "available_at": "2026-10-09"}],
           "s16_e": float("nan"), "s16_c": float("nan"),
           "canonical_evidence_verified": True}
    report = financial_result(raw, estimated_trusted=True, canonical_trusted=True)
    assert report["s16_e"] is None and report["s16_c"] is None
    assert financial_result({**raw, "price": float("inf")})["price"] is None


def test_openrouter_free_caps_are_hard_ceiling():
    from dataclasses import replace
    p = policy()
    for changed in ({"daily_request_cap": 51}, {"minute_request_cap": 21}):
        with pytest.raises(Blocked, match="OPENROUTER_FREE_PLAN_QUOTA_CEILING"):
            replace(p, **changed).validate(2000000000)
