from __future__ import annotations

from collections.abc import Mapping

from core.scoring.math import coverage, wa


ROUTE_NAMES = {
    "F10": "Fundamental Hypergrowth",
    "I10": "Inflection / Re-rating",
    "D10": "Distressed Recovery",
    "B10": "Biotech / Binary Catalyst",
    "R10": "Regime / Theme / Deep-Tech",
    "Q10": "Squeeze / Reflexivity",
}


def _q(f: Mapping[str, float | None]) -> float | None:
    return wa({
        "S8": (1.0, f.get("S8")),
        "S9": (1.0, f.get("S9")),
        "S10": (1.0, f.get("S10")),
        "S12": (1.0, f.get("S12")),
        "S14": (1.0, f.get("S14")),
    })


def distressed_components(f: Mapping[str, float | None]) -> tuple[float | None, float | None, float | None]:
    a_d = wa({
        "DebtImprovement": (1.0, f.get("DEBT_IMPROVEMENT")),
        "FCFInflection": (1.0, f.get("FCF_INFLECTION")),
        "MarginRecovery": (1.0, f.get("MARGIN_RECOVERY")),
        "CostReset": (1.0, f.get("COST_RESET")),
        "DemandRecovery": (1.0, f.get("DEMAND_RECOVERY")),
    })
    c_d = wa({
        "Refinancing": (1.0, f.get("REFINANCING")),
        "Restructuring": (1.0, f.get("RESTRUCTURING")),
        "AssetSale": (1.0, f.get("ASSET_SALE")),
        "DebtExchange": (1.0, f.get("DEBT_EXCHANGE")),
        "BankruptcyExit": (1.0, f.get("BANKRUPTCY_EXIT")),
        "MajorCostReduction": (1.0, f.get("MAJOR_COST_REDUCTION")),
    })
    v_d = wa({
        "LiquidityImprovement": (1.0, f.get("LIQUIDITY_IMPROVEMENT")),
        "DebtMaturityImprovement": (1.0, f.get("DEBT_MATURITY_IMPROVEMENT")),
        "FundingAccess": (1.0, f.get("FUNDING_ACCESS_D")),
        "Continuity": (1.0, f.get("CONTINUITY_D")),
    })
    return a_d, c_d, v_d


def biotech_components(f: Mapping[str, float | None]) -> tuple[float | None, float | None, float | None, float | None]:
    u_b = wa({
        "rNPVMC": (0.55, f.get("RNPVMC")),
        "IndicationTAMMC": (0.25, f.get("INDICATION_TAMMC")),
        "PlatformOptionality": (0.20, f.get("PLATFORM_OPTIONALITY")),
    })
    a_b = wa({
        "ClinicalEvidence": (0.40, f.get("CLINICAL_EVIDENCE")),
        "TrialProgress": (0.25, f.get("TRIAL_PROGRESS")),
        "PartnerValidation": (0.20, f.get("PARTNER_VALIDATION")),
        "EvidenceMomentum": (0.15, f.get("EVIDENCE_MOMENTUM")),
    })
    c_b = f.get("C_B")
    v_b = wa({
        "CashRunway": (0.45, f.get("CASH_RUNWAY_B")),
        "FundingAccess": (0.20, f.get("FUNDING_ACCESS_B")),
        "DilutionQuality": (0.20, f.get("DILUTION_QUALITY_B")),
        "ExecutionReadiness": (0.15, f.get("EXECUTION_READINESS_B")),
    })
    return u_b, a_b, c_b, v_b


def q10(f: Mapping[str, float | None]) -> float | None:
    legs = {
        "SIF": (0.20, f.get("SIF")),
        "DTC": (0.15, f.get("DTC")),
        "BORROW": (0.15, f.get("BORROW")),
        "GAMMA": (0.15, f.get("GAMMA")),
        "FLOAT": (0.10, f.get("FLOAT_Q")),
        "VOLACC": (0.10, f.get("VOLACC")),
        "MOM": (0.10, f.get("MOM_Q")),
        "CAT": (0.05, f.get("CAT_Q")),
    }
    present = sum(1 for _, value in legs.values() if value is not None)
    stress_present = sum(
        1 for key in ("SIF", "DTC", "BORROW", "GAMMA")
        if f.get(key) is not None
    )
    if present < 4 or stress_present < 2:
        return None
    return wa(legs)


def route_scores(f: Mapping[str, float | None]) -> dict[str, float | None]:
    q = _q(f)
    a_d, c_d, v_d = distressed_components(f)
    u_b, a_b, c_b, v_b = biotech_components(f)
    scores = {
        "F10": wa({
            "U": (0.22, f.get("U")),
            "A": (0.22, f.get("A")),
            "C": (0.16, f.get("C")),
            "M": (0.15, f.get("M")),
            "G": (0.08, f.get("G")),
            "V": (0.10, f.get("V")),
            "Q": (0.07, q),
        }),
        "I10": wa({
            "U": (0.20, f.get("U")),
            "A": (0.27, f.get("A")),
            "C": (0.20, f.get("C")),
            "M": (0.15, f.get("M")),
            "G": (0.08, f.get("G")),
            "V": (0.07, f.get("V")),
            "Q": (0.03, q),
        }),
        "D10": wa({
            "U": (0.15, f.get("U")),
            "A_D": (0.30, a_d),
            "C_D": (0.22, c_d),
            "M": (0.13, f.get("M")),
            "G": (0.10, f.get("G")),
            "V_D": (0.10, v_d),
        }),
        "B10": wa({
            "U_B": (0.20, u_b),
            "A_B": (0.15, a_b),
            "C_B": (0.30, c_b),
            "M": (0.10, f.get("M")),
            "G": (0.05, f.get("G")),
            "V_B": (0.20, v_b),
        }),
        "R10": wa({
            "U": (0.20, f.get("U")),
            "A": (0.15, f.get("A")),
            "C": (0.15, f.get("C")),
            "M": (0.15, f.get("M")),
            "G": (0.25, f.get("G")),
            "V": (0.10, f.get("V")),
        }),
        "Q10": q10(f),
    }
    return scores


def ranked_routes(scores: Mapping[str, float | None]) -> list[tuple[str, float]]:
    return sorted(
        ((name, float(value)) for name, value in scores.items() if value is not None),
        key=lambda item: (-item[1], item[0]),
    )


def route_blend(scores: Mapping[str, float | None]) -> tuple[float | None, str | None, str | None]:
    ranked = ranked_routes(scores)
    if not ranked:
        return None, None, None
    primary_name, primary = ranked[0]
    if len(ranked) == 1:
        return primary, primary_name, None
    secondary_name, secondary = ranked[1]
    return 0.85 * primary + 0.15 * secondary, primary_name, secondary_name


def essential_legs(route: str, f: Mapping[str, float | None]) -> dict[str, float | None]:
    a_d, c_d, v_d = distressed_components(f)
    u_b, a_b, c_b, v_b = biotech_components(f)
    if route == "F10":
        return {"U":f.get("U"),"A":f.get("A"),"C":f.get("C"),"M":f.get("M"),"V":f.get("V")}
    if route == "I10":
        return {"A":f.get("A"),"C":f.get("C"),"U":f.get("U"),"M":f.get("M"),"V":f.get("V")}
    if route == "D10":
        return {"A_D":a_d,"C_D":c_d,"V_D":v_d,"M":f.get("M")}
    if route == "B10":
        return {"U_B":u_b,"A_B":a_b,"C_B":c_b,"V_B":v_b}
    if route == "R10":
        return {"G":f.get("G"),"U":f.get("U"),"C":f.get("C"),"M":f.get("M"),"V":f.get("V")}
    if route == "Q10":
        ranked = sorted(
            [(k, f.get(k)) for k in ("SIF","DTC","BORROW","GAMMA") if f.get(k) is not None],
            key=lambda x: float(x[1]), reverse=True,
        )[:2]
        result = {k:v for k,v in ranked}
        result.update({"VOLACC":f.get("VOLACC"),"MOM":f.get("MOM_Q")})
        return result
    return {}


def essential_coverage(route: str, f: Mapping[str, float | None]) -> float:
    legs = essential_legs(route, f)
    if not legs:
        return 0.0
    return 100.0 * sum(v is not None for v in legs.values()) / len(legs)


def bottleneck_penalty(route: str, f: Mapping[str, float | None]) -> float | None:
    legs = essential_legs(route, f)
    values = [float(v) for v in legs.values() if v is not None]
    if not values:
        return None
    essential_min = min(values)
    return min(15.0, 0.50 * max(0.0, 60.0 - essential_min))


def route_gate(route: str, f: Mapping[str, float | None]) -> bool:
    a_d, c_d, v_d = distressed_components(f)
    u_b, a_b, c_b, v_b = biotech_components(f)
    if route == "F10":
        return all(v is not None for v in (f.get("A"),f.get("C"),f.get("DF10"),f.get("V"))) and (
            f["A"] >= 65 and f["C"] >= 50 and f["DF10"] >= 60 and f["V"] >= 50
        )
    if route == "I10":
        return all(v is not None for v in (f.get("A"),f.get("C"),f.get("DF10"),f.get("V"))) and (
            f["A"] >= 70 and f["C"] >= 55 and f["DF10"] >= 55 and f["V"] >= 45
        )
    if route == "D10":
        return all(v is not None for v in (a_d,c_d,v_d)) and (
            a_d >= 60 and c_d >= 60 and v_d >= 55
        )
    if route == "B10":
        return all(v is not None for v in (c_b,v_b,f.get("RNPVMC"))) and (
            c_b >= 70 and v_b >= 65 and f["RNPVMC"] >= 60
        )
    if route == "R10":
        return all(v is not None for v in (f.get("G"),f.get("M"),f.get("C"),f.get("V"))) and (
            f["G"] >= 70 and f["M"] >= 55 and f["C"] >= 50 and f["V"] >= 45
        )
    if route == "Q10":
        stress = [f.get(k) for k in ("SIF","DTC","BORROW","GAMMA")]
        return (
            sum(v is not None and v >= 70 for v in stress) >= 2
            and f.get("VOLACC") is not None and f["VOLACC"] >= 60
            and f.get("MOM_Q") is not None and f["MOM_Q"] >= 60
        )
    return False
