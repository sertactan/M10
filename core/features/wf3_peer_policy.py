from __future__ import annotations

from dataclasses import dataclass


POLICY_VERSION = "WF3_PEER_POLICY_V1_2026-10-07"

MARKET_CAP_BUCKETS = (
    ("MICRO", 0.0, 300_000_000.0),
    ("SMALL", 300_000_000.0, 2_000_000_000.0),
    ("MID", 2_000_000_000.0, 10_000_000_000.0),
    ("LARGE", 10_000_000_000.0, 200_000_000_000.0),
    ("MEGA", 200_000_000_000.0, float("inf")),
)

BUCKET_ORDER = ("MICRO", "SMALL", "MID", "LARGE", "MEGA")


def market_cap_bucket(market_cap: float | None) -> str | None:
    if market_cap is None or market_cap <= 0:
        return None
    value = float(market_cap)
    for name, low, high in MARKET_CAP_BUCKETS:
        if low <= value < high:
            return name
    return None


def profitability_state(
    *,
    ttm_revenue: float | None,
    ttm_operating_income: float | None,
    ttm_fcf: float | None,
) -> str | None:
    """Freeze WF3 profitability-state categories from PIT TTM evidence.

    PROFITABLE_FCF: positive trailing free cash flow.
    OPERATING_PROFITABLE: non-positive/missing FCF but positive operating income.
    PRE_PROFIT_REVENUE: positive revenue but no positive operating income/FCF.
    PRE_REVENUE_OR_BINARY: revenue is zero/negative when explicitly known.
    UNKNOWN: not emitted; missing evidence fails closed.
    """
    if ttm_fcf is not None and ttm_fcf > 0:
        return "PROFITABLE_FCF"
    if ttm_operating_income is not None and ttm_operating_income > 0:
        return "OPERATING_PROFITABLE"
    if ttm_revenue is not None and ttm_revenue > 0:
        return "PRE_PROFIT_REVENUE"
    if ttm_revenue is not None and ttm_revenue <= 0:
        return "PRE_REVENUE_OR_BINARY"
    return None


def adjacent_buckets(bucket: str) -> tuple[str, ...]:
    if bucket not in BUCKET_ORDER:
        return ()
    i = BUCKET_ORDER.index(bucket)
    out = [bucket]
    if i > 0:
        out.append(BUCKET_ORDER[i - 1])
    if i + 1 < len(BUCKET_ORDER):
        out.append(BUCKET_ORDER[i + 1])
    return tuple(out)


@dataclass(frozen=True)
class ExpansionStage:
    name: str
    require_industry: bool
    require_sector: bool
    allowed_buckets: tuple[str, ...] | None
    require_profitability: bool


def expansion_stages(bucket: str) -> tuple[ExpansionStage, ...]:
    """Monotonic N<30 peer expansion; as-of month and route never relax."""
    adjacent = adjacent_buckets(bucket)
    return (
        ExpansionStage("E0_EXACT", True, True, (bucket,), True),
        ExpansionStage("E1_DROP_PROFITABILITY", True, True, (bucket,), False),
        ExpansionStage("E2_ADJACENT_BUCKET", True, True, adjacent, False),
        ExpansionStage("E3_DROP_INDUSTRY", False, True, adjacent, False),
        ExpansionStage("E4_ALL_BUCKETS_IN_SECTOR", False, True, None, False),
        ExpansionStage("E5_ROUTE_ONLY", False, False, None, False),
    )
