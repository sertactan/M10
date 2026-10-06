from __future__ import annotations

import pytest

from core.historical.s16_feature_engine import (
    canonical_attention,
    canonical_catalyst,
    canonical_momentum_acceleration,
    canonical_short_pressure,
    canonical_social_velocity,
    canonical_volume_ignition,
    weighted_available,
)


def test_weighted_available_renormalizes_missing_legs() -> None:
    value = weighted_available(
        {"a": 80.0, "b": None, "c": 40.0},
        {"a": 0.50, "b": 0.25, "c": 0.25},
    )
    assert value == pytest.approx((80 * .50 + 40 * .25) / .75)


def test_canonical_short_pressure_full_formula() -> None:
    value = canonical_short_pressure(
        si_to_float=80,
        days_to_cover=60,
        borrow_pressure=70,
        ftd_pressure=50,
        si_acceleration=90,
    )
    assert value == pytest.approx(72.0)


def test_canonical_short_pressure_renormalizes_missing_vendor_legs() -> None:
    value = canonical_short_pressure(
        si_to_float=80,
        days_to_cover=60,
        borrow_pressure=None,
        ftd_pressure=None,
        si_acceleration=90,
    )
    expected = (80 * .50 + 60 * .20 + 90 * .05) / (.50 + .20 + .05)
    assert value == pytest.approx(expected)


def test_canonical_volume_ignition_full_and_no_premarket() -> None:
    full = canonical_volume_ignition(
        rvol=90,
        float_turnover=80,
        volume_acceleration=70,
        premarket_turnover=60,
    )
    assert full == pytest.approx(80.0)

    daily_only = canonical_volume_ignition(
        rvol=90,
        float_turnover=80,
        volume_acceleration=70,
        premarket_turnover=None,
    )
    expected = (90 * .40 + 80 * .30 + 70 * .20) / .90
    assert daily_only == pytest.approx(expected)


def test_canonical_momentum_acceleration_formula() -> None:
    value = canonical_momentum_acceleration(
        return_1d=80,
        return_acceleration=70,
        range_expansion=90,
        close_location=100,
    )
    assert value == pytest.approx(83.5)


def test_canonical_catalyst_six_leg_formula() -> None:
    value = canonical_catalyst(
        materiality=100,
        surprise=80,
        credibility=90,
        market_cap_impact=70,
        novelty=60,
        immediacy=100,
    )
    expected = (
        100 * .25 + 80 * .20 + 90 * .15
        + 70 * .15 + 60 * .10 + 100 * .15
    )
    assert value == pytest.approx(expected)


def test_catalyst_requires_majority_or_falls_back() -> None:
    value = canonical_catalyst(
        materiality=100,
        surprise=None,
        credibility=None,
        market_cap_impact=None,
        novelty=None,
        immediacy=None,
        fallback=65,
    )
    assert value == pytest.approx(65.0)


def test_social_concentration_penalizes_single_source_burst() -> None:
    diverse = canonical_social_velocity(
        mention_velocity=80,
        unique_author_velocity=80,
        concentration_risk=0,
    )
    concentrated = canonical_social_velocity(
        mention_velocity=80,
        unique_author_velocity=80,
        concentration_risk=100,
    )
    assert diverse == pytest.approx(80.0)
    assert concentrated == pytest.approx(60.0)


def test_attention_combines_social_news_search_and_cross_platform() -> None:
    value = canonical_attention(
        social_velocity=80,
        news_velocity=60,
        search_velocity=70,
        cross_platform=100,
    )
    assert value == pytest.approx(75.0)
