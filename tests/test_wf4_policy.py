from core.historical.wf4_policy import (
    POLICY_VERSION,
    hmg5,
    percentile_rank_midrank,
    xr_score,
)


def test_wf4_policy_version_and_hmg5() -> None:
    assert POLICY_VERSION == "WF4_HISTORICAL_POLICY_V1_2026-10-07"
    assert hmg5(90,60,30) == 68.0
    assert hmg5(None,60,30) is None


def test_percentile_rank_uses_midrank_ties() -> None:
    assert percentile_rank_midrank(20,[10,20,20,30]) == 50.0


def test_xr_exact_n50_and_route_expansion() -> None:
    exact=[{"RB":float(i),"route":"F10","market_cap_bucket":"SMALL"} for i in range(50)]
    r=xr_score(rb=49,route="F10",market_cap_bucket="SMALL",exact_rows=exact,route_rows=exact)
    assert r.scope=="ROUTE_BUCKET"
    assert r.peer_n==50
    assert r.score is not None

    small=[{"RB":float(i),"route":"F10","market_cap_bucket":"SMALL"} for i in range(10)]
    other=[{"RB":float(i),"route":"F10","market_cap_bucket":"MID"} for i in range(30)]
    r2=xr_score(rb=20,route="F10",market_cap_bucket="SMALL",exact_rows=small,route_rows=small+other)
    assert r2.scope=="ROUTE"
    assert r2.peer_n==40
    assert r2.status=="LOW_CONFIDENCE_N_30_49"

    r3=xr_score(rb=20,route="F10",market_cap_bucket="SMALL",exact_rows=small,route_rows=small)
    assert r3.score is None
    assert r3.status=="INSUFFICIENT_N_LT_30"
