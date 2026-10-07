from __future__ import annotations

from dataclasses import dataclass

from core.scoring.math import clip
from core.historical.s153_controls import cohort_similarity


POLICY_VERSION = "WF4_HISTORICAL_POLICY_V1_2026-10-07"


def hmg5(
    winner5_similarity: float | None,
    near_miss5_similarity: float | None,
    hard_similarity: float | None,
) -> float | None:
    """Magnitude-5 historical score.

    Canonical S15.3 says M5 uses the historical 5X cohort. WF4 Policy V1
    freezes the analogous HMG construction:
    winner = FM252>=5, near miss = 3<=FM252<5, hard = FM252<3.
    """
    if None in (winner5_similarity, near_miss5_similarity, hard_similarity):
        return None
    return clip(
        50.0
        + 0.40 * (float(winner5_similarity) - float(near_miss5_similarity))
        + 0.10 * (float(winner5_similarity) - float(hard_similarity))
    )


def percentile_rank_midrank(value: float, peers: list[float]) -> float | None:
    """0..100 percentile rank using midrank for ties."""
    xs=[float(x) for x in peers]
    if not xs:
        return None
    below=sum(x < value for x in xs)
    equal=sum(x == value for x in xs)
    return 100.0 * (below + 0.5 * equal) / len(xs)


@dataclass(frozen=True)
class XRResult:
    score: float | None
    peer_n: int
    scope: str
    status: str


def xr_score(
    *,
    rb: float | None,
    route: str | None,
    market_cap_bucket: str | None,
    exact_rows: list[dict],
    route_rows: list[dict],
) -> XRResult:
    """Cross-sectional rarity with explicit WF4 expansion.

    Canonical exact cohort: same month x route x market-cap bucket.
    Policy V1 expansion when N<50: same month x route (all buckets).
    If expanded N<30 -> N/A.
    """
    if rb is None or not route or not market_cap_bucket:
        return XRResult(None,0,"NONE","MISSING_TARGET")

    exact=[
        float(row["RB"])
        for row in exact_rows
        if row.get("RB") is not None
        and row.get("route") == route
        and row.get("market_cap_bucket") == market_cap_bucket
    ]
    if len(exact) >= 50:
        return XRResult(
            percentile_rank_midrank(float(rb),exact),
            len(exact),
            "ROUTE_BUCKET",
            "NORMAL",
        )

    expanded=[
        float(row["RB"])
        for row in route_rows
        if row.get("RB") is not None and row.get("route") == route
    ]
    if len(expanded) < 30:
        return XRResult(None,len(expanded),"ROUTE","INSUFFICIENT_N_LT_30")
    status="NORMAL" if len(expanded) >= 50 else "LOW_CONFIDENCE_N_30_49"
    return XRResult(
        percentile_rank_midrank(float(rb),expanded),
        len(expanded),
        "ROUTE",
        status,
    )
