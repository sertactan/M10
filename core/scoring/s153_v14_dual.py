from __future__ import annotations

from collections.abc import Mapping

from core.scoring.math import accel_score, clip, clip01, wa


def _score(f: Mapping[str, float | None], *keys: str) -> float | None:
    for key in keys:
        value = f.get(key)
        if value is not None:
            return float(value)
    return None


def route_confidence(f: Mapping[str, float | None]) -> float | None:
    """V1.3 confidence-weighted robust-destination route confidence."""
    dc = _score(f, "V14_DC", "DATA_COVERAGE")
    eq = _score(f, "V14_EQ", "SOURCE_QUALITY")
    rp = _score(f, "V14_RP", "ROUTE_PURITY")
    st = _score(f, "V14_ST", "PARAMETER_STABILITY")
    pit = _score(f, "V14_PIT", "PIT_INTEGRITY")
    if any(value is None for value in (dc, eq, rp, st, pit)):
        return None
    return clip(
        0.25 * dc
        + 0.25 * eq
        + 0.20 * rp
        + 0.15 * st
        + 0.15 * pit
    )


def route_blend_alpha(rc: float | None) -> float | None:
    if rc is None:
        return None
    # Exact recovered V1.3 rule. Alpha is deliberately capped at 0.60.
    return 0.60 * clip01((float(rc) - 50.0) / 50.0)


def robust_destination(
    *,
    base_df10: float | None,
    df_bear: float | None,
    df_base: float | None,
    df_bull: float | None,
    alpha: float | None,
) -> tuple[float | None, float | None]:
    if any(v is None for v in (df_bear, df_base, df_bull)):
        return None, None
    rdf10 = clip(
        0.35 * float(df_bear)
        + 0.50 * float(df_base)
        + 0.15 * float(df_bull)
    )
    if base_df10 is None or alpha is None:
        return rdf10, None
    df10_v13 = clip(
        (1.0 - float(alpha)) * float(base_df10)
        + float(alpha) * rdf10
    )
    return rdf10, df10_v13


def destination_uncertainty(
    *,
    mc_bear: float | None,
    mc_base: float | None,
    mc_bull: float | None,
    explicit_du: float | None = None,
) -> tuple[float | None, float | None]:
    if explicit_du is not None:
        du = clip(float(explicit_du))
        return du, min(10.0, 0.10 * du)
    if any(v is None for v in (mc_bear, mc_base, mc_bull)):
        return None, None
    if float(mc_base) <= 0:
        return None, None
    dispersion = 100.0 * (
        float(mc_bull) - float(mc_bear)
    ) / (2.0 * float(mc_base))
    du = clip(dispersion)
    return du, min(10.0, 0.10 * du)


def assumption_burden(f: Mapping[str, float | None]) -> tuple[float | None, float | None]:
    explicit = _score(f, "V14_AB", "ASSUMPTION_BURDEN")
    if explicit is not None:
        ab = clip(explicit)
    else:
        keys = (
            "GROWTH_STRETCH",
            "MARGIN_STRETCH",
            "MULTIPLE_STRETCH",
            "FUNDING_STRETCH",
            "EXECUTION_STRETCH",
        )
        values = [_score(f, key) for key in keys]
        # The recovered formula is WA(component list) without distinct weights.
        # Treating the unweighted WA as equal-unit weights preserves that notation.
        if any(v is None for v in values):
            return None, None
        ab = wa({key: (1.0, value) for key, value in zip(keys, values, strict=True)})
    if ab is None:
        return None, None
    abp = min(10.0, 0.12 * max(0.0, float(ab) - 35.0))
    return float(ab), abp


def route_disagreement(f: Mapping[str, float | None]) -> tuple[float | None, float | None]:
    explicit = _score(f, "V14_ROUTE_GAP", "ROUTE_GAP")
    if explicit is not None:
        gap = abs(float(explicit))
    else:
        primary = _score(f, "V14_ROUTE_DF10_PRIMARY")
        secondary = _score(f, "V14_ROUTE_DF10_SECONDARY")
        if primary is None or secondary is None:
            return None, None
        gap = abs(primary - secondary)
    rdp = min(8.0, 0.20 * max(0.0, gap - 15.0))
    return gap, rdp


def m10_confirmation(
    *,
    df10_v13: float | None,
    mch10: float | None,
    etrq: float | None,
    rer: float | None,
    cmag: float | None,
    fcvx: float | None,
    hmg10: float | None,
    pir: float | None,
    dup: float | None,
    abp: float | None,
    rdp: float | None,
) -> tuple[float | None, float | None, int]:
    legs = {
        "DF10_V13": (0.30, df10_v13),
        "MCH10": (0.15, mch10),
        "ETRQ": (0.15, etrq),
        "RER": (0.15, rer),
        "CMAG": (0.10, cmag),
        "FCVX": (0.05, fcvx),
        "HMG10": (0.10, hmg10),
    }
    present = sum(1 for _, value in legs.values() if value is not None)
    raw = wa(legs) if present >= 5 else None
    if raw is None or any(v is None for v in (pir, dup, abp, rdp)):
        return raw, None, present
    final = clip(
        float(raw)
        - 0.10 * float(pir)
        - float(dup)
        - float(abp)
        - float(rdp)
    )
    return raw, final, present


def confirmation_bonus(m10_c: float | None, dmg: float | None) -> float | None:
    if m10_c is None or dmg is None:
        return None
    if m10_c < 65.0 or dmg > 10.0:
        return 0.0
    return min(3.0, 0.30 * (m10_c - 65.0))


def disagreement_penalty(dmg: float | None) -> float | None:
    if dmg is None:
        return None
    return min(4.0, 0.20 * max(0.0, float(dmg) - 10.0))


def confirmation_gap_closure(
    *,
    dmg_now: float | None,
    dmg_3m_ago: float | None,
    explicit_cgc: float | None = None,
) -> float | None:
    if explicit_cgc is not None:
        return clip(explicit_cgc)
    if dmg_now is None or dmg_3m_ago is None:
        return None
    return accel_score(float(dmg_3m_ago) - float(dmg_now), 15.0)


def destination_route_acceleration(f: Mapping[str, float | None]) -> float | None:
    explicit = _score(f, "V14_DRA", "DRA")
    if explicit is not None:
        return clip(explicit)
    current = _score(f, "V14_ROUTE_DF10", "ROUTE_DF10")
    prior_1m = _score(f, "V14_ROUTE_DF10_1M_AGO", "ROUTE_DF10_1M_AGO")
    prior_3m = _score(f, "V14_ROUTE_DF10_3M_AGO", "ROUTE_DF10_3M_AGO")
    if any(v is None for v in (current, prior_1m, prior_3m)):
        return None
    one_month = accel_score(float(current) - float(prior_1m), 10.0)
    three_month = accel_score(float(current) - float(prior_3m), 20.0)
    return clip(0.60 * one_month + 0.40 * three_month)


def cycle_acceleration(
    f: Mapping[str, float | None],
    *,
    dra: float | None,
    cgc: float | None,
) -> float | None:
    dema = _score(f, "V14_DEMA", "DEMA")
    scta = _score(f, "V14_SCTA", "SCTA")
    mca = _score(f, "V14_MCA", "MCA")
    capa = _score(f, "V14_CAPA", "CAPA")
    if any(v is None for v in (dema, scta, mca, capa, dra, cgc)):
        return None
    return clip(
        0.25 * dema
        + 0.20 * scta
        + 0.20 * mca
        + 0.15 * capa
        + 0.10 * float(dra)
        + 0.10 * float(cgc)
    )


def asset_acceleration(
    f: Mapping[str, float | None],
    *,
    dra: float | None,
    cgc: float | None,
) -> float | None:
    rqa = _score(f, "V14_RQA", "RQA")
    tda = _score(f, "V14_TDA", "TDA")
    fra = _score(f, "V14_FRA", "FRA")
    cra = _score(f, "V14_CRA", "CRA")
    if any(v is None for v in (rqa, tda, fra, cra, dra, cgc)):
        return None
    return clip(
        0.25 * rqa
        + 0.20 * tda
        + 0.15 * fra
        + 0.15 * cra
        + 0.15 * float(dra)
        + 0.10 * float(cgc)
    )


def early_asymmetric_score(
    f: Mapping[str, float | None],
    *,
    dra: float | None,
    cgc: float | None,
) -> tuple[float | None, str | None, dict[str, float | None]]:
    explicit = _score(f, "V14_EA10", "EA10")
    if explicit is not None:
        return clip(explicit), "EXPLICIT", {"CA10": None, "AA10": None, "SPIN_ACCEL": None}

    ca10 = cycle_acceleration(f, dra=dra, cgc=cgc)
    aa10 = asset_acceleration(f, dra=dra, cgc=cgc)
    spin = _score(f, "V14_SPIN_ACCEL", "SPIN_ACCEL")

    route_code = _score(f, "V14_EA_ROUTE_CODE")
    if route_code is not None:
        code = int(round(route_code))
        if code == 1:
            return ca10, "CYCLE", {"CA10": ca10, "AA10": aa10, "SPIN_ACCEL": spin}
        if code == 2:
            return aa10, "ASSET", {"CA10": ca10, "AA10": aa10, "SPIN_ACCEL": spin}
        if code == 3:
            return spin, "SPIN", {"CA10": ca10, "AA10": aa10, "SPIN_ACCEL": spin}
        return None, None, {"CA10": ca10, "AA10": aa10, "SPIN_ACCEL": spin}

    available = [
        ("CYCLE", ca10),
        ("ASSET", aa10),
        ("SPIN", spin),
    ]
    available = [(name, value) for name, value in available if value is not None]
    if len(available) == 1:
        name, value = available[0]
        return float(value), name, {"CA10": ca10, "AA10": aa10, "SPIN_ACCEL": spin}
    return None, None, {"CA10": ca10, "AA10": aa10, "SPIN_ACCEL": spin}


def progress_gate(
    f: Mapping[str, float | None],
    *,
    dra: float | None,
    cgc: float | None,
) -> tuple[bool, int]:
    route_evidence = _score(f, "V14_ROUTE_EVIDENCE_ACCEL", "ROUTE_EVIDENCE_ACCEL")
    mi = _score(f, "MI")
    checks = (
        dra is not None and dra >= 70.0,
        cgc is not None and cgc >= 60.0,
        route_evidence is not None and route_evidence >= 70.0,
        mi is not None and mi >= 60.0,
    )
    count = sum(bool(value) for value in checks)
    return count >= 2, count


def early_boost(ea10: float | None, gate_pass: bool) -> float | None:
    if ea10 is None:
        return None
    if ea10 < 75.0 or not gate_pass:
        return 0.0
    return min(5.0, 0.40 * (ea10 - 65.0))


def early_stall_penalty(ea10: float | None) -> float | None:
    if ea10 is None:
        return None
    return min(4.0, 0.20 * max(0.0, 55.0 - ea10))
