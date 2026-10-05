from __future__ import annotations

import math

from core.scoring.math import clip


def magnitude_gap(m5: float | None, m10: float | None) -> float | None:
    if m5 is None or m10 is None:
        return None
    return float(m5) - float(m10)


def near_miss_penalty(maggap: float | None) -> float | None:
    if maggap is None:
        return None
    return min(12.0, 0.50 * max(0.0, float(maggap) - 8.0))


def horizon_penalty(t10: float | None) -> float | None:
    if t10 is None:
        return None
    return min(8.0, 0.40 * max(0.0, 65.0 - float(t10)))


def core153(s152: float | None, m10: float | None, t10: float | None) -> float | None:
    if s152 is None or m10 is None or t10 is None:
        return None
    return math.exp(
        0.45 * math.log(max(float(s152), 1.0))
        + 0.30 * math.log(max(float(m10), 1.0))
        + 0.25 * math.log(max(float(t10), 1.0))
    )


def final_s153(core: float | None, nmp: float | None, hp: float | None) -> float | None:
    if core is None or nmp is None or hp is None:
        return None
    return clip(float(core) - float(nmp) - float(hp))
