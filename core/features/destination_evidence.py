from __future__ import annotations

from dataclasses import dataclass
from statistics import median


@dataclass(frozen=True)
class SupportedMCResult:
    supported_mc: float | None
    valid_methods: tuple[str, ...]
    equity_estimates: dict[str, float]
    model_fit_penalty: float
    blockers: tuple[str, ...]


def capped_peer_multiple(
    *,
    peer_p90: float | None,
    peer_median: float | None,
) -> float | None:
    """Canonical V1.2 multiple cap: min(P90_peer, 2 * Median_peer)."""
    if peer_p90 is None or peer_median is None:
        return None
    if peer_p90 <= 0 or peer_median <= 0:
        return None
    return min(float(peer_p90), 2.0 * float(peer_median))


def supported_mc_fundamental_inflection(
    *,
    revenue_12: float | None,
    ebitda_12: float | None,
    fcf_12: float | None,
    sales_multiple: float | None,
    ebitda_multiple: float | None,
    fcf_multiple: float | None,
    net_debt: float | None,
) -> SupportedMCResult:
    """Canonical F10/I10 SupportedMC from valid positive equity estimates.

    SalesEq   = Revenue12 * M_sales - NetDebt
    EBITDAEq  = EBITDA12 * M_ebitda - NetDebt
    FCFEq     = FCF12 * M_fcf
    Supported = median(valid positive equity estimates)

    The canonical spec permits a single valuation method but applies a
    ModelFit -15 adjustment. We expose that penalty as evidence; this function
    does not manufacture MODEL_FIT itself.
    """
    blockers: list[str] = []
    equity: dict[str, float] = {}

    if net_debt is None:
        blockers.append("NET_DEBT_MISSING")
    else:
        nd = float(net_debt)
        if revenue_12 is not None and sales_multiple is not None:
            value = float(revenue_12) * float(sales_multiple) - nd
            if value > 0:
                equity["SALES"] = value
        if ebitda_12 is not None and ebitda_multiple is not None:
            value = float(ebitda_12) * float(ebitda_multiple) - nd
            if value > 0:
                equity["EBITDA"] = value

    if fcf_12 is not None and fcf_multiple is not None:
        value = float(fcf_12) * float(fcf_multiple)
        if value > 0:
            equity["FCF"] = value

    if not equity:
        blockers.append("NO_VALID_POSITIVE_EQUITY_ESTIMATE")
        return SupportedMCResult(
            supported_mc=None,
            valid_methods=(),
            equity_estimates={},
            model_fit_penalty=0.0,
            blockers=tuple(dict.fromkeys(blockers)),
        )

    supported = float(median(equity.values()))
    penalty = 15.0 if len(equity) == 1 else 0.0
    return SupportedMCResult(
        supported_mc=supported,
        valid_methods=tuple(sorted(equity)),
        equity_estimates=equity,
        model_fit_penalty=penalty,
        blockers=tuple(dict.fromkeys(blockers)),
    )


def supported_mc_distressed(
    *,
    normalized_ebitda_12: float | None,
    peer_multiple: float | None,
    post_restructuring_net_debt: float | None,
    restructuring_evidence_factor: float | None,
) -> float | None:
    """Canonical D10 supported market cap with evidence discount."""
    if None in (
        normalized_ebitda_12,
        peer_multiple,
        post_restructuring_net_debt,
        restructuring_evidence_factor,
    ):
        return None
    factor = float(restructuring_evidence_factor)
    if factor not in {1.00, 0.80, 0.60, 0.35}:
        raise ValueError("restructuring_evidence_factor must be canonical 1.00/0.80/0.60/0.35")
    undiscounted = (
        float(normalized_ebitda_12) * float(peer_multiple)
        - float(post_restructuring_net_debt)
    )
    if undiscounted <= 0:
        return None
    return undiscounted * factor


def supported_mc_biotech(
    *,
    pipeline_rnpv: float | None,
    net_cash: float | None,
) -> float | None:
    """Canonical B10: probability-adjusted pipeline rNPV + net cash."""
    if pipeline_rnpv is None or net_cash is None:
        return None
    value = float(pipeline_rnpv) + float(net_cash)
    return value if value > 0 else None


def plausible_ceiling_mc(
    *,
    route_peer_p99_market_cap: float | None,
    route_peer_n: int | None,
    evidence_backed_comparable_mc: float | None,
) -> float | None:
    """Canonical MCH ceiling with the N<30 fail-closed rule."""
    comparable = (
        float(evidence_backed_comparable_mc)
        if evidence_backed_comparable_mc is not None and evidence_backed_comparable_mc > 0
        else None
    )
    peer = None
    if (
        route_peer_p99_market_cap is not None
        and route_peer_p99_market_cap > 0
        and route_peer_n is not None
        and route_peer_n >= 30
    ):
        peer = float(route_peer_p99_market_cap)

    if peer is None and comparable is None:
        return None
    if peer is None:
        return comparable
    if comparable is None:
        return peer
    return max(peer, comparable)
