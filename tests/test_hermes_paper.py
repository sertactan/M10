from core.hermes_team.paper import preview_paper_position


def example():
    return {"symbol": "TEST", "as_of": "2026-10-10T00:00:00Z",
            "price": 50, "stop": 45, "capital": 100_000,
            "risk_fraction": .005, "spread_fraction": .002,
            "slippage_fraction": .005, "fee_usd": 1}


def test_paper_never_live():
    r = preview_paper_position(example())
    assert r["status"] == "PAPER_PREVIEW_ONLY"
    assert not r["broker_request_created"] and not r["canonical_signal"]
    assert r["max_estimated_loss_usd"] <= 500
    assert r["quantity"] >= 1


def test_unsafe_paper_scenarios_blocked():
    for changed in ({"stop": 55}, {"risk_fraction": .25}, {"capital": -3},
                    {"price": 0}, {"price": float("nan")}, {"as_of": "2026-10-10"},
                    {"fee_usd": 5000}, {"symbol": "A/B"}):
        r = preview_paper_position({**example(), **changed})
        assert r["status"] == "NO_TRADE", changed


def test_bad_schema_extra_live_trade_order_blocked():
    r = preview_paper_position({**example(), "broker": "IBKR"})
    assert r["status"] == "NO_TRADE"
