from __future__ import annotations

import math
from collections.abc import Mapping
from statistics import pstdev

from core.scoring.math import clip, wa


def router_scores(f: Mapping[str, float | None]) -> dict[str, float | None]:
    compounder = wa({
        "SG": (0.20, f.get("SG")),
        "RR": (0.20, f.get("RR")),
        "OL": (0.15, f.get("OL_ROUTER")),
        "MOAT": (0.15, f.get("MOAT_ROUTER")),
        "PSC": (0.15, f.get("PSC")),
        "BS": (0.15, f.get("BS_ROUTER")),
    })
    inflection = wa({
        "GA": (0.20, f.get("GA_ROUTER")),
        "MI": (0.20, f.get("MI_ROUTER")),
        "CAT": (0.15, f.get("CAT_ROUTER")),
        "UE": (0.15, f.get("UE_ROUTER")),
        "MSG": (0.15, f.get("MSG")),
        "BS": (0.15, f.get("BS_ROUTER")),
    })
    cyclical = wa({
        "CR": (0.20, f.get("CR")),
        "BS": (0.20, f.get("BS_ROUTER")),
        "CP": (0.15, f.get("CP")),
        "MSG": (0.15, f.get("MSG")),
        "NEP": (0.15, f.get("NEP")),
        "PSC": (0.15, f.get("PSC")),
    })
    return {"C": compounder, "I": inflection, "Y": cyclical}


def historical_h(winner_similarity: float | None, control_similarity: float | None) -> float | None:
    if winner_similarity is None or control_similarity is None:
        return None
    return clip(50.0 + 0.5 * (winner_similarity - control_similarity))


def n61(f: Mapping[str, float | None]) -> float | None:
    return wa({
        "DPF": (0.30, f.get("DPF")),
        "GD": (0.20, f.get("GD")),
        "ONE": (0.15, f.get("ONE")),
        "CYCLE": (0.15, f.get("CYCLE")),
        "INV": (0.10, f.get("INV")),
        "PRICE": (0.10, f.get("PRICE_NORM_RISK")),
    })


def gate6(f: Mapping[str, float | None]) -> float | None:
    return wa({
        "SG": (0.20, f.get("SG")),
        "RR": (0.15, f.get("RR")),
        "OL": (0.15, f.get("OL_ROUTER")),
        "MOAT": (0.15, f.get("MOAT_ROUTER")),
        "PSC": (0.20, f.get("PSC")),
        "MCR": (0.15, f.get("MCR")),
    })


def false_positive_risk(f: Mapping[str, float | None]) -> float | None:
    return wa({
        "DNR": (0.25, f.get("DNR")),
        "GDR": (0.20, f.get("GDR")),
        "DILR": (0.15, f.get("DILR")),
        "AQR": (0.15, f.get("AQR")),
        "PPR": (0.15, f.get("PPR")),
        "VR": (0.10, f.get("VR")),
    })


def s1(dna: float | None, router: float | None, h: float | None, risk_n61: float | None) -> float | None:
    if None in (dna, router, h, risk_n61):
        return None
    return clip(0.55 * dna + 0.25 * router + 0.20 * h - 0.15 * risk_n61)


def s2(dna: float | None, g6: float | None, h: float | None, fpr: float | None) -> float | None:
    if None in (dna, g6, h, fpr):
        return None
    return clip(0.50 * dna + 0.30 * g6 + 0.20 * h - 0.20 * fpr)


def s3(dna: float | None, router: float | None, h: float | None) -> float | None:
    if None in (dna, router, h):
        return None
    return clip(0.55 * dna + 0.25 * router + 0.20 * h)


def s14(f: Mapping[str, float | None]) -> tuple[float | None, dict[str, float | None]]:
    bq = f.get("B_Q")
    d_q = f.get("S6")
    sl_q = f.get("S7")
    mj_q = f.get("S11")
    ce_q = f.get("S12")
    s13 = f.get("S13")
    core_legs = [bq, d_q, sl_q, mj_q, ce_q]
    if any(x is None for x in core_legs) or s13 is None:
        return None, {"EQ_CORE": None, "CONFLICT_PENALTY": None, "FORENSIC_PENALTY": None}
    assert bq is not None and d_q is not None and sl_q is not None and mj_q is not None and ce_q is not None
    eq_core = math.exp(
        0.20 * math.log(max(bq, 1.0))
        + 0.20 * math.log(max(d_q, 1.0))
        + 0.15 * math.log(max(sl_q, 1.0))
        + 0.20 * math.log(max(mj_q, 1.0))
        + 0.25 * math.log(max(ce_q, 1.0))
    )
    sigma = pstdev([bq, d_q, sl_q, mj_q, ce_q])
    conflict = min(10.0, 0.20 * sigma)
    forensic = min(15.0, 0.15 * (100.0 - s13))
    return clip(eq_core - conflict - forensic), {
        "EQ_CORE": eq_core,
        "CONFLICT_PENALTY": conflict,
        "FORENSIC_PENALTY": forensic,
    }


def company_quality(f: Mapping[str, float | None], s14_score: float | None) -> float | None:
    return wa({
        "S8": (1.0, f.get("S8")),
        "S9": (1.0, f.get("S9")),
        "S10": (1.0, f.get("S10")),
        "S12": (1.0, f.get("S12")),
        "S14": (1.0, s14_score),
    })
