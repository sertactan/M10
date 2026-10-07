from __future__ import annotations

from dataclasses import dataclass
from math import floor
from typing import Iterable

from core.features.wf3_peer_policy import POLICY_VERSION, expansion_stages


@dataclass(frozen=True)
class PeerObservation:
    security_id: str
    as_of_month: str
    route: str
    sector: str
    industry: str
    market_cap_bucket: str
    profitability_state: str
    market_cap: float | None = None
    sales_multiple: float | None = None
    ebitda_multiple: float | None = None
    fcf_multiple: float | None = None


@dataclass(frozen=True)
class PeerMetricStats:
    n: int
    median: float | None
    p90: float | None
    p99: float | None
    status: str


@dataclass(frozen=True)
class PeerCohortResult:
    cohort_n: int
    cohort_status: str
    expansion_stage: str
    sales: PeerMetricStats
    ebitda: PeerMetricStats
    fcf: PeerMetricStats
    market_cap: PeerMetricStats
    blockers: tuple[str, ...]


def _quantile_type7(values: list[float], q: float) -> float | None:
    """Deterministic linear quantile (Hyndman-Fan type 7 / common default).

    This is an implementation convention for the percentile operator, not a
    new S15.3 model weight or threshold.
    """
    if not values:
        return None
    if not 0.0 <= q <= 1.0:
        raise ValueError("q must be in [0,1]")
    xs = sorted(float(v) for v in values)
    if len(xs) == 1:
        return xs[0]
    h = (len(xs) - 1) * q
    lo = floor(h)
    hi = min(lo + 1, len(xs) - 1)
    frac = h - lo
    return xs[lo] + frac * (xs[hi] - xs[lo])


def _stats(values: Iterable[float | None]) -> PeerMetricStats:
    xs = [float(v) for v in values if v is not None and float(v) > 0]
    n = len(xs)
    if n < 30:
        return PeerMetricStats(
            n=n, median=None, p90=None, p99=None, status="INSUFFICIENT_N_LT_30"
        )
    status = "NORMAL" if n >= 50 else "LOW_CONFIDENCE_N_30_49"
    return PeerMetricStats(
        n=n,
        median=_quantile_type7(xs, 0.50),
        p90=_quantile_type7(xs, 0.90),
        p99=_quantile_type7(xs, 0.99),
        status=status,
    )


def exact_peer_match(target: PeerObservation, candidate: PeerObservation) -> bool:
    """Canonical exact-cohort key before any peer expansion.

    same as-of month × route × sector/industry × market-cap bucket ×
    profitability state.

    Sector AND industry are required here. The canonical source does not freeze
    the N<30 expansion sequence, so this module never relaxes fields silently.
    """
    if candidate.security_id == target.security_id:
        return False
    return (
        candidate.as_of_month == target.as_of_month
        and candidate.route == target.route
        and candidate.sector == target.sector
        and candidate.industry == target.industry
        and candidate.market_cap_bucket == target.market_cap_bucket
        and candidate.profitability_state == target.profitability_state
    )


def evaluate_exact_peer_cohort(
    target: PeerObservation,
    observations: Iterable[PeerObservation],
) -> PeerCohortResult:
    peers = [row for row in observations if exact_peer_match(target, row)]
    cohort_n = len(peers)

    blockers: list[str] = []
    if cohort_n < 30:
        cohort_status = "EXPANSION_REQUIRED_RULE_UNSPECIFIED"
        blockers.append("PEER_N_LT_30")
        blockers.append("PEER_EXPANSION_RULE_UNSPECIFIED")
    elif cohort_n < 50:
        cohort_status = "LOW_CONFIDENCE_N_30_49"
    else:
        cohort_status = "NORMAL"

    sales = _stats(row.sales_multiple for row in peers)
    ebitda = _stats(row.ebitda_multiple for row in peers)
    fcf = _stats(row.fcf_multiple for row in peers)
    market_cap = _stats(row.market_cap for row in peers)

    for key, stats in (
        ("SALES_MULTIPLE", sales),
        ("EBITDA_MULTIPLE", ebitda),
        ("FCF_MULTIPLE", fcf),
        ("MARKET_CAP", market_cap),
    ):
        if stats.n < 30:
            blockers.append(f"{key}_PEER_N_LT_30")

    return PeerCohortResult(
        cohort_n=cohort_n,
        cohort_status=cohort_status,
        expansion_stage="E0_EXACT",
        sales=sales,
        ebitda=ebitda,
        fcf=fcf,
        market_cap=market_cap,
        blockers=tuple(dict.fromkeys(blockers)),
    )



def _matches_stage(
    target: PeerObservation,
    candidate: PeerObservation,
    *,
    stage,
) -> bool:
    if candidate.security_id == target.security_id:
        return False
    if candidate.as_of_month != target.as_of_month:
        return False
    if candidate.route != target.route:
        return False
    if stage.require_sector and candidate.sector != target.sector:
        return False
    if stage.require_industry and candidate.industry != target.industry:
        return False
    if stage.allowed_buckets is not None and candidate.market_cap_bucket not in stage.allowed_buckets:
        return False
    if stage.require_profitability and candidate.profitability_state != target.profitability_state:
        return False
    return True


def evaluate_peer_cohort(
    target: PeerObservation,
    observations: Iterable[PeerObservation],
) -> PeerCohortResult:
    """WF3 Peer Policy V1 expansion.

    The first stage with at least 30 peers is selected. If no stage reaches 30,
    all percentile legs remain N/A. Month and route never relax.
    """
    rows = list(observations)
    selected = []
    selected_stage = None
    for stage in expansion_stages(target.market_cap_bucket):
        candidates = [
            row for row in rows
            if _matches_stage(target, row, stage=stage)
        ]
        if len(candidates) >= 30:
            selected = candidates
            selected_stage = stage
            break

    if selected_stage is None:
        return PeerCohortResult(
            cohort_n=0,
            cohort_status="INSUFFICIENT_AFTER_EXPANSION",
            expansion_stage="NONE",
            sales=_stats([]),
            ebitda=_stats([]),
            fcf=_stats([]),
            market_cap=_stats([]),
            blockers=(
                "PEER_N_LT_30_AFTER_EXPANSION",
                f"PEER_POLICY={POLICY_VERSION}",
            ),
        )

    cohort_n = len(selected)
    cohort_status = "NORMAL" if cohort_n >= 50 else "LOW_CONFIDENCE_N_30_49"
    sales = _stats(row.sales_multiple for row in selected)
    ebitda = _stats(row.ebitda_multiple for row in selected)
    fcf = _stats(row.fcf_multiple for row in selected)
    market_cap = _stats(row.market_cap for row in selected)

    blockers: list[str] = []
    for key, stats in (
        ("SALES_MULTIPLE", sales),
        ("EBITDA_MULTIPLE", ebitda),
        ("FCF_MULTIPLE", fcf),
        ("MARKET_CAP", market_cap),
    ):
        if stats.n < 30:
            blockers.append(f"{key}_PEER_N_LT_30")

    return PeerCohortResult(
        cohort_n=cohort_n,
        cohort_status=cohort_status,
        expansion_stage=selected_stage.name,
        sales=sales,
        ebitda=ebitda,
        fcf=fcf,
        market_cap=market_cap,
        blockers=tuple(dict.fromkeys(blockers)),
    )
