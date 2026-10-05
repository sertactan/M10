from __future__ import annotations

import math
from collections.abc import Mapping

from core.models.s153_v12_contracts import S153V12Input, S153V12Result
from core.routes.s153_v12 import (
    biotech_components,
    bottleneck_penalty,
    distressed_components,
    essential_coverage,
    route_blend,
    route_gate,
    route_scores,
)
from core.scoring.dna60 import control12, core48, dna60
from core.scoring.math import clip, wa
from core.scoring.s1_s14 import (
    company_quality,
    false_positive_risk,
    gate6,
    historical_h,
    n61,
    router_scores,
    s1,
    s2,
    s3,
    s14,
)
from core.scoring.s153_v12_components import (
    catalyst_score,
    cmag,
    destination_score,
    etrq,
    execution_readiness,
    fcvx,
    flow,
    magnitude,
    market_cap_headroom,
    market_confirmation,
    market_ignition,
    pir,
    precursor_acceleration,
    precursor_velocity_x,
    pv,
    regime_acceleration,
    regime_fit,
    rer,
    revision_acceleration,
    t10,
    t15,
    viability,
)


class CanonicalInputError(ValueError):
    pass


def _validate_scores(values: Mapping[str, float | None]) -> None:
    raw_allowed = {
        "MEDIAN_DOLLAR_VOLUME_20",
        "SUPPORTED_MC_12_FI",
        "SUPPORTED_MC_12_D",
        "SUPPORTED_MC_12_B",
        "SUPPORTED_MC_12_R",
        "PLAUSIBLE_CEILING_MC",
    }
    for key, value in values.items():
        if value is None or key in raw_allowed:
            continue
        if not 0.0 <= float(value) <= 100.0:
            raise CanonicalInputError(f"{key} must be canonical 0..100 score, got {value}")


def _max_router(router: Mapping[str, float | None]) -> float | None:
    values = [float(v) for v in router.values() if v is not None]
    return max(values) if values else None


def _u(control: Mapping[str, float | None], f: Mapping[str, float | None], e: float | None, fc: float | None, rr: float | None) -> float | None:
    return wa({
        "MCR": (0.35, control.get("MCR")),
        "TAMMC": (0.20, control.get("TAMMC")),
        "ETRQ": (0.15, e),
        "OPT": (0.10, f.get("OPT")),
        "FCVX": (0.10, fc),
        "RER": (0.10, rr),
    })


def _q_destination(f: Mapping[str, float | None]) -> float | None:
    return wa({
        "FloatTightness": (0.35, f.get("FLOAT_TIGHTNESS")),
        "ShortStress": (0.25, f.get("SHORT_STRESS")),
        "GammaConvexity": (0.20, f.get("GAMMA_CONVEXITY")),
        "TurnoverAcceleration": (0.20, f.get("TURNOVER_ACCELERATION")),
    })


def _supported_mc_key(route: str | None) -> str | None:
    if route in {"F10", "I10"}:
        return "SUPPORTED_MC_12_FI"
    if route == "D10":
        return "SUPPORTED_MC_12_D"
    if route == "B10":
        return "SUPPORTED_MC_12_B"
    if route == "R10":
        return "SUPPORTED_MC_12_R"
    return None


def _s152(
    *,
    rb: float | None,
    df10: float | None,
    x: float | None,
    h10: float | None,
    xr: float | None,
    pir_score: float | None,
    bp: float | None,
) -> float | None:
    # Canonical spec only permits H10/XR positive legs to be absent with re-normalization.
    if any(v is None for v in (rb, df10, x, pir_score, bp)):
        return None
    positive = {
        "RB": (0.55, rb),
        "DF10": (0.15, df10),
        "X": (0.10, x),
        "H10": (0.10, h10),
        "XR": (0.10, xr),
    }
    pos = wa(positive)
    if pos is None:
        return None
    return clip(pos - 0.10 * float(pir_score) - float(bp))


def _confidence(f: Mapping[str, float | None]) -> float | None:
    required = [f.get("DATA_COVERAGE"), f.get("SOURCE_QUALITY"), f.get("PIT_INTEGRITY"), f.get("MODEL_FIT")]
    if any(v is None for v in required):
        return None
    return clip(
        0.40 * float(required[0])
        + 0.25 * float(required[1])
        + 0.20 * float(required[2])
        + 0.15 * float(required[3])
    )


def _verdict(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= 85:
        return "Elite 12M 10X Confirmation"
    if score >= 80:
        return "Precision 10X Candidate"
    if score >= 75:
        return "Strong 10X Watch"
    if score >= 65:
        return "10X Discovery"
    if score >= 55:
        return "Early / Route Dependent"
    return "Low 12M 10X Feasibility"


class S153V12Model:
    model_id = "S15.3_V1.2"
    canonical_formula_version = "MERIDYEN_S15.3_CANONICAL_FINAL_v1.0"

    def analyze(self, data: S153V12Input) -> S153V12Result:
        if data.as_of.tzinfo is None:
            raise CanonicalInputError("as_of must be timezone-aware")
        _validate_scores(data.features)

        c48, families = core48(data.discovery_factors)
        c12 = control12(data.control_factors)
        dna = dna60(c48, c12)

        base_features = dict(data.features)
        base_features.setdefault("MCR", data.control_factors.get("MCR"))
        base_features.setdefault("DIL", data.control_factors.get("DIL"))
        base_features.setdefault("UE_ROUTER", data.control_factors.get("UE"))
        base_features.setdefault("MOAT_ROUTER", data.control_factors.get("MOAT"))

        router = router_scores(base_features)
        r = _max_router(router)
        h = historical_h(base_features.get("WINNER_SIM"), base_features.get("CONTROL_SIM"))
        risk61 = n61(base_features)
        g6 = gate6(base_features)
        fpr = false_positive_risk(base_features)

        s1_score = s1(dna, r, h, risk61)
        s2_score = s2(dna, g6, h, fpr)
        s3_score = s3(dna, r, h)
        s14_score, s14_diag = s14(base_features)
        base_features["S14"] = s14_score
        cq = company_quality(base_features, s14_score)

        etrq_score = etrq(base_features)
        fcvx_score = fcvx(base_features)
        rer_score = rer(base_features)
        c_score = catalyst_score(base_features)
        m_score = market_confirmation(base_features)
        g_score = regime_fit(base_features)
        v_score = viability(base_features)
        a_score = precursor_acceleration(base_features)
        x_score = precursor_velocity_x(base_features)
        cmag_score = cmag(base_features)
        pir_score = pir(base_features)

        model_features = dict(base_features)
        model_features.update({
            "U": _u(data.control_factors, base_features, etrq_score, fcvx_score, rer_score),
            "A": a_score,
            "C": c_score,
            "M": m_score,
            "G": g_score,
            "V": v_score,
        })

        routes = route_scores(model_features)
        rb, primary_route, secondary_route = route_blend(routes)

        if primary_route == "Q10":
            df5 = df10 = _q_destination(model_features)
        else:
            supported_key = _supported_mc_key(primary_route)
            supported_mc = base_features.get(supported_key) if supported_key else None
            df5 = destination_score(supported_mc, data.current_market_cap, 5.0)
            df10 = destination_score(supported_mc, data.current_market_cap, 10.0)

        mch5 = market_cap_headroom(base_features.get("PLAUSIBLE_CEILING_MC"), data.current_market_cap, 5.0)
        mch10 = market_cap_headroom(base_features.get("PLAUSIBLE_CEILING_MC"), data.current_market_cap, 10.0)

        model_features.update({"DF5": df5, "DF10": df10})
        bp = bottleneck_penalty(primary_route, model_features) if primary_route else None

        s152 = _s152(
            rb=rb,
            df10=df10,
            x=x_score,
            h10=base_features.get("H10"),
            xr=base_features.get("XR"),
            pir_score=pir_score,
            bp=bp,
        )

        m10_raw, m10_score, m10_legs = magnitude(
            df=df10,mch=mch10,etrq_score=etrq_score,rer_score=rer_score,
            cmag_score=cmag_score,fcvx_score=fcvx_score,hmg=base_features.get("HMG10"),
            pir_score=pir_score,
        )
        m5_raw, m5_score, m5_legs = magnitude(
            df=df5,mch=mch5,etrq_score=etrq_score,rer_score=rer_score,
            cmag_score=cmag_score,fcvx_score=fcvx_score,hmg=base_features.get("HMG5"),
            pir_score=pir_score,
        )

        maggap = (m5_score - m10_score) if m5_score is not None and m10_score is not None else None
        nmp = min(12.0, 0.50 * max(0.0, maggap - 8.0)) if maggap is not None else None

        pv_score = pv(base_features)
        mi_score = market_ignition(base_features)
        rev_score = revision_acceleration(base_features)
        ra_score = regime_acceleration(base_features)
        flow_score = flow(base_features)
        exec_score = execution_readiness(base_features)
        exec15_score = execution_readiness(base_features, horizon15=True)
        time_components = {
            "CT": base_features.get("CT"),
            "CT15": base_features.get("CT15"),
            "PV": pv_score,
            "MI": mi_score,
            "REV": rev_score,
            "RA": ra_score,
            "FLOW": flow_score,
            "EXEC": exec_score,
            "EXEC15": exec15_score,
        }
        t10_score, t10_legs = t10(time_components)
        t15_score, _t15_legs = t15(time_components)

        hp = min(8.0, 0.40 * max(0.0, 65.0 - t10_score)) if t10_score is not None else None
        core153 = None
        if s152 is not None and m10_score is not None and t10_score is not None:
            core153 = math.exp(
                0.45 * math.log(max(s152, 1.0))
                + 0.30 * math.log(max(m10_score, 1.0))
                + 0.25 * math.log(max(t10_score, 1.0))
            )

        route_coverage = essential_coverage(primary_route, model_features) if primary_route else 0.0
        missing: list[str] = []
        if s152 is None:
            missing.append("S15.2")
        if m10_score is None or m10_legs < 5:
            missing.append("M10>=5/7")
        if t10_score is None or t10_legs < 5:
            missing.append("T10>=5/7")
        if route_coverage < 70.0:
            missing.append("selected route essential coverage>=70%")

        final_score = None
        if not missing and core153 is not None and nmp is not None and hp is not None:
            final_score = clip(core153 - nmp - hp)

        gate = route_gate(primary_route, model_features) if primary_route else False
        conf = _confidence(base_features)

        magnitude_near_miss = bool(m5_score is not None and m10_score is not None and m5_score >= 80 and m10_score < 70)
        five_x_dominant = bool(maggap is not None and maggap >= 15)
        horizon_false_positive = bool(t10_score is not None and t15_score is not None and t10_score < 65 and t15_score >= 75)
        horizon_risk = bool(t10_score is not None and t15_score is not None and (t15_score - t10_score) >= 15)

        precision = bool(
            final_score is not None and final_score >= 80
            and m10_score is not None and m10_score >= 70
            and t10_score is not None and t10_score >= 70
            and df10 is not None and df10 >= 60
            and base_features.get("XR") is not None and base_features["XR"] >= 99
            and base_features.get("HMG10") is not None
            and gate
            and conf is not None and conf >= 70
        )
        strong = bool(
            final_score is not None and final_score >= 75
            and m10_score is not None and m10_score >= 65
            and t10_score is not None and t10_score >= 65
            and gate
        )
        discovery = bool(final_score is not None and final_score >= 65)

        if missing:
            status = "INCONCLUSIVE"
        elif precision:
            status = "PRECISION_CONFIRMED_12M_10X"
        elif final_score is not None and final_score >= 80:
            status = "HIGH_SCORE_NOT_CONFIRMED"
        elif strong:
            status = "STRONG_10X_WATCH"
        elif discovery:
            status = "10X_DISCOVERY"
        else:
            status = "NO_CANONICAL_GATE_STATUS"

        a_d, c_d, v_d = distressed_components(model_features)
        u_b, a_b, c_b, v_b = biotech_components(model_features)
        components: dict[str, float | None] = {
            **{f"CORE48_{k.upper()}": v for k,v in families.items()},
            "CORE48": c48,"CONTROL12": c12,"DNA60": dna,
            "ROUTER_C": router["C"],"ROUTER_I": router["I"],"ROUTER_Y": router["Y"],"ROUTER_R": r,
            "H": h,"N61": risk61,"G6": g6,"FPR": fpr,
            "S1": s1_score,"S2": s2_score,"S3": s3_score,"S14": s14_score,"COMPANY_QUALITY": cq,
            **s14_diag,
            "U":model_features.get("U"),"A":a_score,"C":c_score,"M":m_score,"G":g_score,"V":v_score,
            "A_D":a_d,"C_D":c_d,"V_D":v_d,"U_B":u_b,"A_B":a_b,"C_B":c_b,"V_B":v_b,
            "RB":rb,"DF5":df5,"DF10":df10,"MCH5":mch5,"MCH10":mch10,
            "ETRQ":etrq_score,"RER":rer_score,"CMAG":cmag_score,"FCVX":fcvx_score,
            "HMG5":base_features.get("HMG5"),"HMG10":base_features.get("HMG10"),
            "H10":base_features.get("H10"),"XR":base_features.get("XR"),"PIR":pir_score,"BP":bp,"X":x_score,
            "S15.2":s152,"M5_RAW":m5_raw,"M5":m5_score,"M10_RAW":m10_raw,"M10":m10_score,
            "MAGGAP":maggap,"NMP":nmp,"CT":base_features.get("CT"),"PV":pv_score,"MI":mi_score,
            "REV":rev_score,"RA":ra_score,"FLOW":flow_score,"EXEC":exec_score,
            "T10":t10_score,"T15":t15_score,"HP":hp,"CORE15.3":core153,"S15.3":final_score,
            "CONFIDENCE":conf,"ROUTE_ESSENTIAL_COVERAGE":route_coverage,
        }
        flags = {
            "MAGNITUDE_NEAR_MISS": magnitude_near_miss,
            "FIVE_X_PROFILE_DOMINANT": five_x_dominant,
            "HORIZON_FALSE_POSITIVE_RISK": horizon_false_positive,
            "HORIZON_RISK": horizon_risk,
            "QUALITY_CONFLICT": bool(s14_score is not None and s14_diag.get("CONFLICT_PENALTY",0) and s14_diag["CONFLICT_PENALTY"] >= 5),
            "SURVIVAL_RISK": bool(v_score is not None and v_score < 50),
            "FORENSIC_REVIEW": bool(s14_score is not None and s14_score < 55),
        }
        return S153V12Result(
            security_id=data.security_id,ticker=data.ticker,as_of=data.as_of,
            score=final_score,status=status,verdict=_verdict(final_score),
            primary_route=primary_route,secondary_route=secondary_route,route_gate=gate,
            confidence=conf,precision_confirmed=precision,strong_watch=strong,discovery=discovery,
            components=components,routes=routes,flags=flags,missing_requirements=tuple(missing),
        )
