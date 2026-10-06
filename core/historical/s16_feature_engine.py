from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


def _clip100(value: float) -> float:
    return min(100.0, max(0.0, float(value)))


def weighted_available(
    values: Mapping[str, float | None],
    weights: Mapping[str, float],
) -> float | None:
    """Weighted mean over available legs, with weights renormalized.

    Missing historical evidence is excluded rather than interpreted as zero.
    """
    pairs = [
        (float(values[key]), float(weight))
        for key, weight in weights.items()
        if values.get(key) is not None
    ]
    if not pairs:
        return None
    total = sum(weight for _, weight in pairs)
    if total <= 0:
        return None
    return _clip100(sum(value * weight for value, weight in pairs) / total)


SHORT_WEIGHTS = {
    "si_to_float": 0.50,
    "days_to_cover": 0.20,
    "borrow_pressure": 0.15,
    "ftd_pressure": 0.10,
    "si_acceleration": 0.05,
}

VOLUME_WEIGHTS = {
    "rvol": 0.40,
    "float_turnover": 0.30,
    "volume_acceleration": 0.20,
    "premarket_turnover": 0.10,
}

MOMENTUM_WEIGHTS = {
    "return_1d": 0.35,
    "return_acceleration": 0.25,
    "range_expansion": 0.20,
    "close_location": 0.20,
}

CATALYST_WEIGHTS = {
    "materiality": 0.25,
    "surprise": 0.20,
    "credibility": 0.15,
    "market_cap_impact": 0.15,
    "novelty": 0.10,
    "immediacy": 0.15,
}

ATTENTION_WEIGHTS = {
    "social_velocity": 0.45,
    "news_velocity": 0.25,
    "search_velocity": 0.20,
    "cross_platform": 0.10,
}


def canonical_short_pressure(
    *,
    si_to_float: float | None,
    days_to_cover: float | None,
    borrow_pressure: float | None = None,
    ftd_pressure: float | None = None,
    si_acceleration: float | None = None,
) -> float | None:
    return weighted_available(
        {
            "si_to_float": si_to_float,
            "days_to_cover": days_to_cover,
            "borrow_pressure": borrow_pressure,
            "ftd_pressure": ftd_pressure,
            "si_acceleration": si_acceleration,
        },
        SHORT_WEIGHTS,
    )


def canonical_volume_ignition(
    *,
    rvol: float | None,
    float_turnover: float | None,
    volume_acceleration: float | None,
    premarket_turnover: float | None = None,
) -> float | None:
    return weighted_available(
        {
            "rvol": rvol,
            "float_turnover": float_turnover,
            "volume_acceleration": volume_acceleration,
            "premarket_turnover": premarket_turnover,
        },
        VOLUME_WEIGHTS,
    )


def canonical_momentum_acceleration(
    *,
    return_1d: float | None,
    return_acceleration: float | None,
    range_expansion: float | None,
    close_location: float | None,
) -> float | None:
    return weighted_available(
        {
            "return_1d": return_1d,
            "return_acceleration": return_acceleration,
            "range_expansion": range_expansion,
            "close_location": close_location,
        },
        MOMENTUM_WEIGHTS,
    )


def canonical_catalyst(
    *,
    materiality: float | None,
    surprise: float | None,
    credibility: float | None,
    market_cap_impact: float | None,
    novelty: float | None,
    immediacy: float | None,
    fallback: float | None = None,
) -> float | None:
    values = {
        "materiality": materiality,
        "surprise": surprise,
        "credibility": credibility,
        "market_cap_impact": market_cap_impact,
        "novelty": novelty,
        "immediacy": immediacy,
    }
    present = sum(value is not None for value in values.values())
    # A one-leg or two-leg "catalyst" would be too easy to overstate. Require a
    # majority of canonical legs; otherwise retain the explicit PIT fallback.
    if present >= 4:
        return weighted_available(values, CATALYST_WEIGHTS)
    return None if fallback is None else _clip100(fallback)


def canonical_social_velocity(
    *,
    mention_velocity: float | None,
    unique_author_velocity: float | None,
    concentration_risk: float | None,
) -> float | None:
    base = weighted_available(
        {
            "mention_velocity": mention_velocity,
            "unique_author_velocity": unique_author_velocity,
        },
        {"mention_velocity": 0.70, "unique_author_velocity": 0.30},
    )
    if base is None:
        return None
    if concentration_risk is None:
        return base
    # ConcentrationRisk is 0..100; a bot/single-author dominated burst may lose
    # at most 25% of the social score. It cannot create a signal.
    penalty = 1.0 - 0.25 * (_clip100(concentration_risk) / 100.0)
    return _clip100(base * penalty)


def canonical_attention(
    *,
    social_velocity: float | None,
    news_velocity: float | None,
    search_velocity: float | None,
    cross_platform: float | None,
) -> float | None:
    return weighted_available(
        {
            "social_velocity": social_velocity,
            "news_velocity": news_velocity,
            "search_velocity": search_velocity,
            "cross_platform": cross_platform,
        },
        ATTENTION_WEIGHTS,
    )


@dataclass(frozen=True)
class S16FeatureEngineVersion:
    version: str = "S16_FEATURE_ENGINE_V1.0"
