from __future__ import annotations

import math
from collections.abc import Iterable, Mapping

from core.scoring.math import clip, mean_top


def similarity(
    target: Mapping[str, float | None],
    candidate: Mapping[str, float | None],
    weights: Mapping[str, float] | None = None,
) -> float | None:
    common = [
        key for key, value in target.items()
        if value is not None and candidate.get(key) is not None
    ]
    if not common:
        return None
    weights = weights or {}
    numerator = 0.0
    denominator = 0.0
    for key in common:
        weight = float(weights.get(key, 1.0))
        diff = float(target[key]) - float(candidate[key])
        numerator += weight * diff * diff
        denominator += weight
    if denominator <= 0:
        return None
    distance = math.sqrt(numerator / denominator) / 100.0
    return 100.0 * (1.0 - min(1.0, max(0.0, distance)))


def cohort_similarity(
    target: Mapping[str, float | None],
    cohort: Iterable[Mapping[str, float | None]],
    weights: Mapping[str, float] | None = None,
    k: int = 5,
) -> float | None:
    sims = [
        score
        for item in cohort
        if (score := similarity(target, item, weights)) is not None
    ]
    return mean_top(sims, k)


def historical_h(winner_similarity: float | None, control_similarity: float | None) -> float | None:
    if winner_similarity is None or control_similarity is None:
        return None
    return clip(50.0 + 0.5 * (winner_similarity - control_similarity))


def h10(
    winner_similarity: float | None,
    near_miss_similarity: float | None,
    failure_similarity: float | None,
) -> float | None:
    if None in (winner_similarity, near_miss_similarity, failure_similarity):
        return None
    return clip(
        50.0
        + 0.35 * (winner_similarity - near_miss_similarity)
        + 0.15 * (winner_similarity - failure_similarity)
    )


def hmg10(
    winner10_similarity: float | None,
    near_miss_similarity: float | None,
    hard_similarity: float | None,
) -> float | None:
    if None in (winner10_similarity, near_miss_similarity, hard_similarity):
        return None
    return clip(
        50.0
        + 0.40 * (winner10_similarity - near_miss_similarity)
        + 0.10 * (winner10_similarity - hard_similarity)
    )
