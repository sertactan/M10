from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from core.scoring.math import accel_score, clip, wa


RECOVERED_FORMULA_VERSION = "S15.3_V1.4_RECOVERED_2026-10-05"


@dataclass(frozen=True)
class V14RecoveredMath:
    base_df10: float
    rdf10: float
    route_confidence: float
    alpha: float
    df10_confirmation: float
    du: float
    dup: float
    abp: float
    rdp: float
    m10_c_raw: float
    m10_c: float
    m10_d: float
    dmg: float
    cb: float
    dp: float
    base_v14_score: float
    final_v14_score: float
    early_asymmetric: bool
    ea_route: str | None
    ea10: float | None
    cgc: float | None
    progress_gate: bool | None
    eab: float
    esp: float
    ea_label: str | None


V13_REQUIRED_FEATURES = (
    "V14_DF_B",
    "V14_DF_M",
    "V14_DF_U",
    "V14_MC_BEAR",
    "V14_MC_BASE",
    "V14_MC_BULL",
    "V14_RC_DC",
    "V14_RC_EQ",
    "V14_RC_RP",
    "V14_RC_ST",
    "V14_RC_PIT",
    "V14_AB",
    "V14_ROUTE_GAP",
)

SPIN_FEATURES = (
    "V14_FRESHNESS",
    "V14_FORCED_SELLER",
    "V14_STANDALONE_INFLECTION",
    "V14_PEER_DISLOCATION",
    "V14_CATALYST",
)

CYCLE_FEATURES = (
    "V14_DEMAND_ACCELERATION",
    "V14_SUPPLY_TIGHTNESS",
    "V14_ASP_TREND",
    "V14_BACKLOG_BOOKBILL",
    "V14_MARGIN_TORQUE",
    "V14_CAPACITY_LEAD_TIME",
)

ASSET_FEATURES = (
    "V14_RESOURCE_QUALITY",
    "V14_TECHNICAL_MATURITY",
    "V14_FUNDING",
    "V14_PERMITTING",
    "V14_COMMODITY_REGIME",
    "V14_CATALYST",
)

CYCLE_EA_FEATURES = ("V14_DEMA", "V14_SCTA", "V14_MCA", "V14_CAPA", "V14_DRA")
ASSET_EA_FEATURES = ("V14_RQA", "V14_TDA", "V14_FRA", "V14_CRA", "V14_DRA")


def _value(features: Mapping[str, float | None], key: str) -> float | None:
    value = features.get(key)
    return None if value is None else float(value)


def missing_v13_features(features: Mapping[str, float | None]) -> tuple[str, ...]:
    return tuple(key for key in V13_REQUIRED_FEATURES if _value(features, key) is None)


def _all(features: Mapping[str, float | None], names: tuple[str, ...]) -> bool:
    return all(_value(features, name) is not None for name in names)


def destination_route_gates(features: Mapping[str, float | None]) -> dict[str, float]:
    """Recovered SPIN/CYCLE/ASSET activation formulas.

    Incomplete routes are omitted rather than imputed.
    """
    active: dict[str, float] = {}
    if _all(features, SPIN_FEATURES):
        spin = (
            0.25 * float(features["V14_FRESHNESS"])
            + 0.20 * float(features["V14_FORCED_SELLER"])
            + 0.20 * float(features["V14_STANDALONE_INFLECTION"])
            + 0.20 * float(features["V14_PEER_DISLOCATION"])
            + 0.15 * float(features["V14_CATALYST"])
        )
        if spin >= 65:
            active["SPIN"] = clip(spin)

    if _all(features, CYCLE_FEATURES):
        demand = float(features["V14_DEMAND_ACCELERATION"])
        supply = float(features["V14_SUPPLY_TIGHTNESS"])
        cycle = (
            0.25 * demand
            + 0.20 * supply
            + 0.15 * float(features["V14_ASP_TREND"])
            + 0.15 * float(features["V14_BACKLOG_BOOKBILL"])
            + 0.15 * float(features["V14_MARGIN_TORQUE"])
            + 0.10 * float(features["V14_CAPACITY_LEAD_TIME"])
        )
        if cycle >= 65 and demand >= 60 and supply >= 60:
            active["CYCLE"] = clip(cycle)

    if _all(features, ASSET_FEATURES):
        asset = (
            0.25 * float(features["V14_RESOURCE_QUALITY"])
            + 0.20 * float(features["V14_TECHNICAL_MATURITY"])
            + 0.15 * float(features["V14_FUNDING"])
            + 0.15 * float(features["V14_PERMITTING"])
            + 0.10 * float(features["V14_COMMODITY_REGIME"])
            + 0.15 * float(features["V14_CATALYST"])
        )
        if asset >= 60:
            active["ASSET"] = clip(asset)
    return active


def _route_confidence(features: Mapping[str, float | None]) -> float:
    return clip(
        0.25 * float(features["V14_RC_DC"])
        + 0.25 * float(features["V14_RC_EQ"])
        + 0.20 * float(features["V14_RC_RP"])
        + 0.15 * float(features["V14_RC_ST"])
        + 0.15 * float(features["V14_RC_PIT"])
    )


def _confirmation_magnitude(
    *,
    features: Mapping[str, float | None],
    base_df10: float,
    mch10: float,
    etrq: float,
    rer: float,
    cmag: float,
    fcvx: float,
    hmg10: float,
    pir: float,
) -> tuple[float, float, float, float, float, float, float, float]:
    rdf10 = (
        0.35 * float(features["V14_DF_B"])
        + 0.50 * float(features["V14_DF_M"])
        + 0.15 * float(features["V14_DF_U"])
    )
    rc = _route_confidence(features)
    alpha = 0.60 * clip((rc - 50.0) / 50.0, 0.0, 1.0)
    df10_c = clip((1.0 - alpha) * base_df10 + alpha * rdf10)

    mc_bear = float(features["V14_MC_BEAR"])
    mc_base = float(features["V14_MC_BASE"])
    mc_bull = float(features["V14_MC_BULL"])
    if mc_base <= 0:
        raise ValueError("V14_MC_BASE must be >0")
    du = clip(100.0 * (mc_bull - mc_bear) / (2.0 * mc_base))
    dup = min(10.0, 0.10 * du)

    ab = float(features["V14_AB"])
    abp = min(10.0, 0.12 * max(0.0, ab - 35.0))

    route_gap = float(features["V14_ROUTE_GAP"])
    rdp = min(8.0, 0.20 * max(0.0, route_gap - 15.0))

    raw = (
        0.30 * df10_c
        + 0.15 * mch10
        + 0.15 * etrq
        + 0.15 * rer
        + 0.10 * cmag
        + 0.05 * fcvx
        + 0.10 * hmg10
    )
    m10_c = clip(raw - 0.10 * pir - dup - abp - rdp)
    return rdf10, rc, alpha, df10_c, du, dup, abp, rdp, raw, m10_c


def _ea10(
    *,
    route: str | None,
    features: Mapping[str, float | None],
    dmg: float,
    mi: float | None,
) -> tuple[float | None, float | None, bool | None, float, float, str | None]:
    if route not in {"CYCLE", "ASSET"}:
        return None, None, None, 0.0, 0.0, None
    prior_dmg = _value(features, "V14_DMG_T_MINUS_3M")
    if prior_dmg is None:
        return None, None, None, 0.0, 0.0, None

    cgc = accel_score(prior_dmg - dmg, 15.0)
    dra = _value(features, "V14_DRA")
    route_evidence = _value(features, "V14_ROUTE_EVIDENCE_ACCEL")

    if route == "CYCLE":
        if not _all(features, CYCLE_EA_FEATURES):
            return None, cgc, None, 0.0, 0.0, None
        ea = wa({
            "DEMA": (0.25, _value(features, "V14_DEMA")),
            "SCTA": (0.20, _value(features, "V14_SCTA")),
            "MCA": (0.20, _value(features, "V14_MCA")),
            "CAPA": (0.15, _value(features, "V14_CAPA")),
            "DRA": (0.10, dra),
            "CGC": (0.10, cgc),
        })
    else:
        if not _all(features, ASSET_EA_FEATURES):
            return None, cgc, None, 0.0, 0.0, None
        ea = wa({
            "RQA": (0.25, _value(features, "V14_RQA")),
            "TDA": (0.20, _value(features, "V14_TDA")),
            "FRA": (0.15, _value(features, "V14_FRA")),
            "CRA": (0.15, _value(features, "V14_CRA")),
            "DRA": (0.15, dra),
            "CGC": (0.10, cgc),
        })

    if ea is None:
        return None, cgc, None, 0.0, 0.0, None

    progress_checks = (
        dra is not None and dra >= 70,
        cgc >= 60,
        route_evidence is not None and route_evidence >= 70,
        mi is not None and mi >= 60,
    )
    progress_gate = sum(bool(x) for x in progress_checks) >= 2
    eab = min(5.0, 0.40 * (ea - 65.0)) if ea >= 75 and progress_gate else 0.0
    esp = min(4.0, 0.20 * max(0.0, 55.0 - ea))

    if ea >= 75 and progress_gate:
        label = "EARLY_ACCELERATING_10X"
    elif ea >= 60:
        label = "EARLY_ASYMMETRIC_WATCH"
    else:
        label = "EARLY_ASYMMETRIC_STALLED"
    return ea, cgc, progress_gate, eab, esp, label


def calculate_recovered_v14(
    *,
    features: Mapping[str, float | None],
    v12_score: float,
    m10_d: float,
    base_df10: float,
    mch10: float,
    etrq: float,
    rer: float,
    cmag: float,
    fcvx: float,
    hmg10: float,
    pir: float,
    mi: float | None,
) -> V14RecoveredMath:
    missing = missing_v13_features(features)
    if missing:
        raise ValueError("Missing recovered V1.3 inputs: " + ", ".join(missing))

    rdf10, rc, alpha, df10_c, du, dup, abp, rdp, raw, m10_c = _confirmation_magnitude(
        features=features,
        base_df10=base_df10,
        mch10=mch10,
        etrq=etrq,
        rer=rer,
        cmag=cmag,
        fcvx=fcvx,
        hmg10=hmg10,
        pir=pir,
    )
    dmg = m10_d - m10_c
    cb = min(3.0, 0.30 * (m10_c - 65.0)) if m10_c >= 65 and dmg <= 10 else 0.0
    dp = min(4.0, 0.20 * max(0.0, dmg - 10.0))
    base_v14 = clip(v12_score + cb - dp)

    early = v12_score >= 65 and (m10_c < 65 or dmg > 10)
    ea_route: str | None = None
    ea10 = cgc = None
    progress_gate = None
    eab = esp = 0.0
    ea_label = None

    if v12_score >= 65 and m10_d >= 65 and (m10_c < 70 or dmg > 10):
        active = destination_route_gates(features)
        if active:
            ea_route = sorted(active.items(), key=lambda item: (-item[1], item[0]))[0][0]
        ea10, cgc, progress_gate, eab, esp, ea_label = _ea10(
            route=ea_route,
            features=features,
            dmg=dmg,
            mi=mi,
        )

    final = clip(base_v14 + eab - esp)
    if m10_c < 70:
        final = min(final, 79.0)

    return V14RecoveredMath(
        base_df10=base_df10,
        rdf10=clip(rdf10),
        route_confidence=rc,
        alpha=alpha,
        df10_confirmation=df10_c,
        du=du,
        dup=dup,
        abp=abp,
        rdp=rdp,
        m10_c_raw=raw,
        m10_c=m10_c,
        m10_d=m10_d,
        dmg=dmg,
        cb=cb,
        dp=dp,
        base_v14_score=base_v14,
        final_v14_score=final,
        early_asymmetric=early,
        ea_route=ea_route,
        ea10=ea10,
        cgc=cgc,
        progress_gate=progress_gate,
        eab=eab,
        esp=esp,
        ea_label=ea_label,
    )
