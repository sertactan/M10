"""Personal scenario S14 via the untouched original geometric aggregation."""
from __future__ import annotations

from core.scoring.s1_s14 import s14 as frozen_s14
from .contracts import personal_result


def assess_personal_s14(models: dict, *, s7=None, s11=None, s12=None) -> dict:
    legs = {"S6": models.get("S6", {}).get("score"),
            "B_Q": models.get("B_Q", {}).get("score"),
            "S13": models.get("S13", {}).get("score"),
            "S7": s7, "S11": s11, "S12": s12}
    missing = [key for key, value in legs.items() if value is None]
    if missing:
        return personal_result("PERSONAL_S14_SCENARIO", missing=missing,
                               status="UNRESOLVED", components={"legs": legs})
    score, decomposition = frozen_s14(legs)
    return personal_result(
        "PERSONAL_S14_SCENARIO", score=score, numeric_result_type="SCENARIO",
        status="SCENARIO_ONLY",
        components={"legs": legs, "geometric": decomposition,
                    "original_zero_s11_preserved": s11 == 0,
                    "original_computation": "core.scoring.s1_s14.s14"})
