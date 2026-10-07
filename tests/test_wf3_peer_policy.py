from core.features.wf3_peer_policy import (
    POLICY_VERSION,
    adjacent_buckets,
    expansion_stages,
    market_cap_bucket,
    profitability_state,
)


def test_wf3_peer_policy_version_is_frozen() -> None:
    assert POLICY_VERSION == "WF3_PEER_POLICY_V1_2026-10-07"


def test_market_cap_buckets_are_explicit_and_non_overlapping() -> None:
    assert market_cap_bucket(299_999_999) == "MICRO"
    assert market_cap_bucket(300_000_000) == "SMALL"
    assert market_cap_bucket(2_000_000_000) == "MID"
    assert market_cap_bucket(10_000_000_000) == "LARGE"
    assert market_cap_bucket(200_000_000_000) == "MEGA"
    assert market_cap_bucket(None) is None


def test_profitability_state_uses_pit_ttm_evidence() -> None:
    assert profitability_state(ttm_revenue=100,ttm_operating_income=-5,ttm_fcf=10) == "PROFITABLE_FCF"
    assert profitability_state(ttm_revenue=100,ttm_operating_income=5,ttm_fcf=-1) == "OPERATING_PROFITABLE"
    assert profitability_state(ttm_revenue=100,ttm_operating_income=-5,ttm_fcf=-1) == "PRE_PROFIT_REVENUE"
    assert profitability_state(ttm_revenue=0,ttm_operating_income=-5,ttm_fcf=-1) == "PRE_REVENUE_OR_BINARY"
    assert profitability_state(ttm_revenue=None,ttm_operating_income=None,ttm_fcf=None) is None


def test_expansion_is_monotonic_and_never_changes_route_or_month_policy() -> None:
    assert adjacent_buckets("MID") == ("MID","SMALL","LARGE")
    stages=expansion_stages("MID")
    assert [s.name for s in stages] == [
        "E0_EXACT","E1_DROP_PROFITABILITY","E2_ADJACENT_BUCKET",
        "E3_DROP_INDUSTRY","E4_ALL_BUCKETS_IN_SECTOR","E5_ROUTE_ONLY",
    ]
    assert stages[0].require_profitability is True
    assert stages[-1].require_sector is False
