from __future__ import annotations

import math
from collections.abc import Iterable, Mapping


def clip(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return min(high, max(low, float(value)))


def clip01(value: float) -> float:
    return clip(value, 0.0, 1.0)


def wa(values: Mapping[str, tuple[float, float | None]]) -> float | None:
    """Canonical weighted average. N/A legs are excluded from numerator/denominator."""
    numerator = 0.0
    denominator = 0.0
    for weight, value in values.values():
        if value is None:
            continue
        numerator += float(weight) * float(value)
        denominator += float(weight)
    if denominator <= 0:
        return None
    return clip(numerator / denominator)


def coverage(values: Mapping[str, tuple[float, float | None]]) -> float:
    total = sum(float(weight) for weight, _ in values.values())
    if total <= 0:
        return 0.0
    present = sum(float(weight) for weight, value in values.values() if value is not None)
    return 100.0 * present / total


def pos_score(value: float, low: float, high: float) -> float:
    if high <= low:
        raise ValueError("high must be greater than low")
    return 100.0 * clip01((float(value) - low) / (high - low))


def neg_score(value: float, good: float, bad: float) -> float:
    if bad <= good:
        raise ValueError("bad must be greater than good")
    return 100.0 * (1.0 - clip01((float(value) - good) / (bad - good)))


def accel_score(delta: float, theta: float) -> float:
    if theta <= 0:
        raise ValueError("theta must be positive")
    scaled = max(-1.0, min(1.0, float(delta) / theta))
    return clip(50.0 + 50.0 * scaled)


def piecewise_score(value: float, knots: Iterable[tuple[float, float]]) -> float:
    points = sorted((float(x), float(y)) for x, y in knots)
    if not points:
        raise ValueError("piecewise score requires knots")
    x = float(value)
    if x <= points[0][0]:
        return clip(points[0][1])
    if x >= points[-1][0]:
        return clip(points[-1][1])
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x0 <= x <= x1:
            ratio = (x - x0) / (x1 - x0)
            return clip(y0 + ratio * (y1 - y0))
    raise AssertionError("unreachable")


def weighted_geometric_mean(values: Mapping[str, tuple[float, float | None]]) -> float | None:
    present = [(float(w), float(v)) for w, v in values.values() if v is not None]
    if not present:
        return None
    denominator = sum(w for w, _ in present)
    if denominator <= 0:
        return None
    return clip(math.exp(sum((w / denominator) * math.log(max(v, 1.0)) for w, v in present)))


def mean(values: Iterable[float]) -> float | None:
    items = [float(x) for x in values]
    return sum(items) / len(items) if items else None


def mean_top(values: Iterable[float], k: int = 5) -> float | None:
    items = sorted((float(x) for x in values), reverse=True)
    return mean(items[:k])
