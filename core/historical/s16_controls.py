from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Iterable


MATCH_WEIGHTS = {
    "market_cap": 0.22,
    "float_shares": 0.20,
    "price": 0.12,
    "adv20": 0.15,
    "volatility20": 0.12,
    "mom5": 0.08,
    "mom20": 0.05,
    "sector": 0.04,
    "listing_age_days": 0.02,
}


class InsufficientControlPool(RuntimeError):
    pass


@dataclass(frozen=True)
class S16MatchSnapshot:
    security_id: str
    ticker: str
    as_of_date: date
    market_cap: float
    float_shares: float
    price: float
    adv20: float
    volatility20: float
    mom5: float
    mom20: float
    sector: str
    listing_age_days: int
    security_type: str = "CS"
    ipo_route: bool = False


@dataclass(frozen=True)
class S16MatchedControl:
    positive_security_id: str
    positive_ticker: str
    as_of_date: date
    control_rank: int
    control_security_id: str
    control_ticker: str
    distance: float


def _log_distance(a: float, b: float, scale: float) -> float:
    if a <= 0 or b <= 0:
        return 1.0
    return min(1.0, abs(math.log(a / b)) / scale)


def _linear_distance(a: float, b: float, scale: float) -> float:
    return min(1.0, abs(float(a) - float(b)) / scale)


def matching_distance(target: S16MatchSnapshot, candidate: S16MatchSnapshot) -> float:
    """PIT-only distance. Deliberately contains no future-return/outcome field."""
    terms = {
        "market_cap": _log_distance(target.market_cap, candidate.market_cap, 2.0),
        "float_shares": _log_distance(target.float_shares, candidate.float_shares, 2.0),
        "price": _log_distance(target.price, candidate.price, 1.5),
        "adv20": _log_distance(target.adv20, candidate.adv20, 2.0),
        "volatility20": _linear_distance(target.volatility20, candidate.volatility20, 1.0),
        "mom5": _linear_distance(target.mom5, candidate.mom5, 2.0),
        "mom20": _linear_distance(target.mom20, candidate.mom20, 4.0),
        "sector": 0.0 if target.sector == candidate.sector else 1.0,
        "listing_age_days": _log_distance(
            max(1.0, target.listing_age_days),
            max(1.0, candidate.listing_age_days),
            2.5,
        ),
    }
    return sum(MATCH_WEIGHTS[key] * terms[key] for key in MATCH_WEIGHTS)


def select_controls(
    positive: S16MatchSnapshot,
    candidates: Iterable[S16MatchSnapshot],
    *,
    n: int = 50,
) -> list[S16MatchedControl]:
    eligible = []
    for candidate in candidates:
        if candidate.security_id == positive.security_id:
            continue
        if candidate.as_of_date != positive.as_of_date:
            continue
        if candidate.security_type != "CS":
            continue
        if candidate.ipo_route != positive.ipo_route:
            continue
        eligible.append((matching_distance(positive, candidate), candidate))

    eligible.sort(key=lambda item: (item[0], item[1].security_id))
    if len(eligible) < n:
        raise InsufficientControlPool(
            f"{positive.ticker} {positive.as_of_date}: need {n} controls, got {len(eligible)}"
        )

    return [
        S16MatchedControl(
            positive_security_id=positive.security_id,
            positive_ticker=positive.ticker,
            as_of_date=positive.as_of_date,
            control_rank=rank,
            control_security_id=candidate.security_id,
            control_ticker=candidate.ticker,
            distance=distance,
        )
        for rank, (distance, candidate) in enumerate(eligible[:n], start=1)
    ]


def build_matched_controls(
    positives: Iterable[S16MatchSnapshot],
    candidates: Iterable[S16MatchSnapshot],
    *,
    controls_per_positive: int = 50,
) -> list[S16MatchedControl]:
    candidate_rows = list(candidates)
    out: list[S16MatchedControl] = []
    for positive in positives:
        out.extend(select_controls(positive, candidate_rows, n=controls_per_positive))
    return out
