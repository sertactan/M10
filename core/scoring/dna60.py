from __future__ import annotations

from collections.abc import Mapping

from core.scoring.math import clip, wa


DISCOVERY_FAMILIES: dict[str, tuple[int, ...]] = {
    "Growth": tuple(range(1, 9)),
    "Quality": tuple(range(9, 15)),
    "Valuation": tuple(range(15, 20)),
    "Momentum": tuple(range(20, 26)),
    "Expectations": tuple(range(26, 30)),
    "Ownership": tuple(range(30, 34)),
    "Inflection": tuple(range(34, 40)),
    "Innovation": tuple(range(40, 45)),
    "Quant": tuple(range(45, 49)),
}

CORE48_WEIGHTS = {
    "Growth": 0.20,
    "Quality": 0.15,
    "Valuation": 0.10,
    "Momentum": 0.10,
    "Expectations": 0.10,
    "Ownership": 0.05,
    "Inflection": 0.15,
    "Innovation": 0.10,
    "Quant": 0.05,
}

CONTROL12_WEIGHTS = {
    "MCR": 0.12,
    "TAMMC": 0.10,
    "GP": 0.12,
    "RPS": 0.10,
    "FPS": 0.10,
    "DIL": 0.10,
    "IROIC": 0.08,
    "ORG": 0.08,
    "UE": 0.07,
    "MOAT": 0.06,
    "CAPINT": 0.04,
    "CONC": 0.03,
}


def _validated(value: float | None) -> float | None:
    if value is None:
        return None
    if not 0.0 <= float(value) <= 100.0:
        raise ValueError(f"canonical factor must be 0..100, got {value}")
    return float(value)


def core48(discovery: Mapping[int, float | None]) -> tuple[float | None, dict[str, float | None]]:
    families: dict[str, float | None] = {}
    for family, indexes in DISCOVERY_FAMILIES.items():
        legs = {
            str(i): (1.0, _validated(discovery.get(i)))
            for i in indexes
        }
        families[family] = wa(legs)
    score = wa({
        family: (weight, families[family])
        for family, weight in CORE48_WEIGHTS.items()
    })
    return score, families


def control12(control: Mapping[str, float | None]) -> float | None:
    return wa({
        key: (weight, _validated(control.get(key)))
        for key, weight in CONTROL12_WEIGHTS.items()
    })


def dna60(core48_score: float | None, control12_score: float | None) -> float | None:
    if core48_score is None or control12_score is None:
        return None
    return clip(0.70 * core48_score + 0.30 * control12_score)
