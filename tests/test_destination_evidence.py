import pytest

from core.features.destination_evidence import (
    capped_peer_multiple,
    plausible_ceiling_mc,
    supported_mc_biotech,
    supported_mc_distressed,
    supported_mc_fundamental_inflection,
)


def test_capped_peer_multiple_uses_min_p90_or_two_times_median() -> None:
    assert capped_peer_multiple(peer_p90=12.0, peer_median=5.0) == 10.0
    assert capped_peer_multiple(peer_p90=8.0, peer_median=5.0) == 8.0


def test_fundamental_supported_mc_uses_median_of_positive_methods() -> None:
    result = supported_mc_fundamental_inflection(
        revenue_12=100.0,
        ebitda_12=20.0,
        fcf_12=10.0,
        sales_multiple=8.0,
        ebitda_multiple=30.0,
        fcf_multiple=40.0,
        net_debt=100.0,
    )
    # Sales=700, EBITDA=500, FCF=400 -> median=500.
    assert result.supported_mc == 500.0
    assert result.valid_methods == ("EBITDA", "FCF", "SALES")
    assert result.model_fit_penalty == 0.0


def test_single_method_is_allowed_but_exposes_model_fit_penalty() -> None:
    result = supported_mc_fundamental_inflection(
        revenue_12=None,
        ebitda_12=None,
        fcf_12=10.0,
        sales_multiple=None,
        ebitda_multiple=None,
        fcf_multiple=40.0,
        net_debt=None,
    )
    assert result.supported_mc == 400.0
    assert result.valid_methods == ("FCF",)
    assert result.model_fit_penalty == 15.0
    assert "NET_DEBT_MISSING" in result.blockers


def test_distressed_supported_mc_applies_canonical_evidence_discount() -> None:
    assert supported_mc_distressed(
        normalized_ebitda_12=100.0,
        peer_multiple=8.0,
        post_restructuring_net_debt=200.0,
        restructuring_evidence_factor=0.80,
    ) == pytest.approx(480.0)
    with pytest.raises(ValueError):
        supported_mc_distressed(
            normalized_ebitda_12=100.0,
            peer_multiple=8.0,
            post_restructuring_net_debt=200.0,
            restructuring_evidence_factor=0.70,
        )


def test_biotech_supported_mc_is_rnpv_plus_net_cash() -> None:
    assert supported_mc_biotech(pipeline_rnpv=750.0, net_cash=250.0) == 1000.0


def test_plausible_ceiling_requires_peer_n_30_or_comparable() -> None:
    assert plausible_ceiling_mc(
        route_peer_p99_market_cap=5000.0,
        route_peer_n=29,
        evidence_backed_comparable_mc=None,
    ) is None
    assert plausible_ceiling_mc(
        route_peer_p99_market_cap=5000.0,
        route_peer_n=29,
        evidence_backed_comparable_mc=4200.0,
    ) == 4200.0
    assert plausible_ceiling_mc(
        route_peer_p99_market_cap=5000.0,
        route_peer_n=30,
        evidence_backed_comparable_mc=4200.0,
    ) == 5000.0
