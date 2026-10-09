"""Dependency-free Hermes V2 safety checks (offline; no provider calls)."""
from __future__ import annotations

import json
import tempfile
from dataclasses import replace
from pathlib import Path

from core.hermes_team.adapters import plugin_response, telegram_message
from core.hermes_team.contracts import financial_result
from core.hermes_team.gateway import check_payload, perform
from core.hermes_team.guard import Blocked, Policy, QuotaGuard
from core.hermes_team.m10_bridge import canonical_s16_from_verified_features
from core.hermes_team.roles import ROLES, route


def denied(op, *, label):
    try:
        op()
    except Blocked:
        print("PASS", label)
        return
    raise AssertionError("FAILED TO BLOCK: " + label)


def run() -> None:
    assert len(ROLES) == 6
    assert route("risk", allow_llm=True)["execution"] == "PYTHON_OR_REVIEW"
    print("PASS six logical roles")
    p = Policy(enabled=True, provider="openrouter", model="test/free:free",
               free_tier_verified=True, nonbillable_account_verified=True,
               verification_expires_epoch=4102444800,
               daily_request_cap=2, minute_request_cap=2)
    request = {"model": p.model, "messages": [{"role": "user", "content": "hi"}],
               "max_tokens": 32}
    denied(lambda: check_payload({**request, "model": "paid"}, p),
           label="model switch denied")
    denied(lambda: check_payload({**request, "stream": True}, p),
           label="stream denied")
    denied(lambda: check_payload({**request, "tools": []}, p),
           label="tools denied")
    denied(lambda: check_payload({**request, "max_tokens": 1000000}, p),
           label="max tokens")
    with tempfile.TemporaryDirectory() as directory:
        g = QuotaGuard(Path(directory) / "guard.sqlite3")
        at = 2000000000
        denied(lambda: g.reserve(request_id="disabled", policy=replace(p, enabled=False),
                                 prompt_bytes=20, now=at), label="disabled")
        denied(lambda: g.reserve(request_id="notfree", policy=replace(p, model="paid"),
                                 prompt_bytes=20, now=at), label="paid model")
        denied(lambda: g.reserve(request_id="notverified",
                                 policy=replace(p, nonbillable_account_verified=False),
                                 prompt_bytes=20, now=at), label="unverified billing")
        g.reserve(request_id="first", policy=p, prompt_bytes=20, now=at)
        denied(lambda: g.reserve(request_id="second", policy=p, prompt_bytes=20,
                                 now=at), label="one LLM at a time")
        g.finish("first")
        g.reserve(request_id="second", policy=p, prompt_bytes=20, now=at)
        g.finish("second")
        denied(lambda: g.reserve(request_id="third", policy=p, prompt_bytes=20,
                                 now=at), label="quota exhausted")
        print("PASS SQLite transaction locks and cleanup")
    with tempfile.TemporaryDirectory() as directory:
        g = QuotaGuard(Path(directory) / "guard.sqlite3")

        def mock_transport(policy, body):
            assert json.loads(body)["model"] == policy.model
            return b'{"choices":[{"message":{"role":"assistant","content":"mock"}}]}'

        response = perform(request, policy=p, guard=g, transport=mock_transport)
        assert response["choices"][0]["message"]["content"] == "mock"
        print("PASS offline network-mocked gateway")
    missing = financial_result({"symbol": "INOD", "s16_c": 100})
    assert missing["s16_c"] is None and missing["decision"] == "INCONCLUSIVE"
    assert canonical_s16_from_verified_features({
        "symbol": "INOD", "s16_c": 99, "canonical_evidence_verified": True,
        "feature_origin": "LLM"
    })["s16_c"] is None
    valid = financial_result({
        "symbol": "INOD", "price": 8.5,
        "price_timestamp": "2026-10-09T16:00:00Z",
        "sources": [{"source": "SEC", "source_ref": "filing",
                     "retrieved_at": "2026-10-09", "available_at": "2026-10-09"}],
        "s16_e": 61, "s16_c": 83, "canonical_evidence_verified": True,
    })
    assert valid["s16_e"] == 61 and valid["s16_c"] is None
    assert "S16-C: INCONCLUSIVE" in telegram_message(valid)
    assert plugin_response(valid)["transport_connected"] is False
    print("PASS financial and adapter contracts (synthetic fixture only)")
    print("ALL_HERMES_V2_SMOKE_TESTS_PASSED")


if __name__ == "__main__":
    run()
