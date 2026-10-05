from __future__ import annotations

from collections.abc import Mapping

from core.scoring.math import accel_score, clip, piecewise_score, pos_score, wa


def etrq(f: Mapping[str, float | None]) -> float | None:
    return wa({
        "OL_Q": (0.35, f.get("OL_Q")),
        "MI_Q": (0.25, f.get("MI_Q")),
        "FCFI_Q": (0.20, f.get("FCFI_Q")),
        "EPSL_Q": (0.20, f.get("EPSL_Q")),
    })


def fcvx(f: Mapping[str, float | None]) -> float | None:
    score = wa({
        "FLOATSIZE": (0.50, f.get("FLOATSIZE")),
        "TURNACC": (0.30, f.get("TURNACC")),
        "SCARCITY": (0.20, f.get("SCARCITY")),
    })
    if score is None:
        return None
    dollar_volume = f.get("MEDIAN_DOLLAR_VOLUME_20")
    if dollar_volume is None:
        return score
    if dollar_volume < 250_000:
        return min(score, 20.0)
    if dollar_volume < 1_000_000:
        return min(score, 40.0)
    if dollar_volume < 5_000_000:
        return min(score, 70.0)
    return score


def rer(f: Mapping[str, float | None]) -> float | None:
    profitshift = f.get("PROFITSHIFT")
    if profitshift is None:
        profitshift = wa({
            "MI_Q": (0.50, f.get("MI_Q")),
            "FCFI_Q": (0.30, f.get("FCFI_Q")),
            "CROSSZERO": (0.20, f.get("CROSSZERO")),
        })
    return wa({
        "PROFITSHIFT": (0.35, profitshift),
        "MODELSHIFT": (0.25, f.get("MODELSHIFT")),
        "BSSHIFT": (0.20, f.get("BSSHIFT")),
        "MULTGAP": (0.20, f.get("MULTGAP")),
    })


def catalyst_score(f: Mapping[str, float | None]) -> float | None:
    return wa({
        "TIME": (0.30, f.get("TIME")),
        "MAG": (0.25, f.get("MAG")),
        "EVID": (0.20, f.get("EVID")),
        "STACK": (0.15, f.get("STACK")),
        "ASYM": (0.10, f.get("ASYM")),
    })


def market_confirmation(f: Mapping[str, float | None]) -> float | None:
    return wa({
        "RS": (0.20, f.get("RS")),
        "H52": (0.10, f.get("H52")),
        "BREAK": (0.20, f.get("BREAK")),
        "STAGE2": (0.15, f.get("STAGE2")),
        "VCP": (0.10, f.get("VCP")),
        "PVACC": (0.25, f.get("PVACC")),
    })


def regime_fit(f: Mapping[str, float | None]) -> float | None:
    return wa({
        "MR": (0.20, f.get("MR")),
        "SRS": (0.25, f.get("SRS")),
        "TB": (0.20, f.get("TB")),
        "UA": (0.20, f.get("UA")),
        "LIQ": (0.15, f.get("LIQ")),
    })


def viability(f: Mapping[str, float | None]) -> float | None:
    return wa({
        "CASH": (0.30, f.get("CASH")),
        "BS": (0.20, f.get("BS_V")),
        "FUND": (0.15, f.get("FUND")),
        "MAT": (0.15, f.get("MAT")),
        "DIL": (0.10, f.get("DIL")),
        "CONT": (0.10, f.get("CONT")),
    })


def precursor_acceleration(f: Mapping[str, float | None]) -> float | None:
    return wa({
        "RBACC": (0.25, f.get("RBACC")),
        "DNAACC": (0.15, f.get("DNAACC")),
        "REVACC": (0.15, f.get("REVACC")),
        "PROFACC": (0.15, f.get("PROFACC")),
        "MOMACC": (0.10, f.get("MOMACC")),
        "VOLACC": (0.10, f.get("VOLACC")),
        "GROWACC": (0.10, f.get("GROWACC")),
    })


def precursor_velocity_x(f: Mapping[str, float | None]) -> float | None:
    return wa({
        "RBV3": (0.30, f.get("RBV3")),
        "RBV6": (0.25, f.get("RBV6")),
        "CATACC": (0.20, f.get("CATACC")),
        "REGACC": (0.15, f.get("REGACC")),
        "VOLACC": (0.10, f.get("VOLACC")),
    })


def cmag(f: Mapping[str, float | None]) -> float | None:
    return wa({
        "MAG": (0.50, f.get("MAG")),
        "EVID": (0.30, f.get("EVID")),
        "STACK": (0.20, f.get("STACK")),
    })


def pir(f: Mapping[str, float | None]) -> float | None:
    return wa({
        "VAL": (0.30, f.get("PIR_VAL")),
        "EXT": (0.25, f.get("PIR_EXT")),
        "DEC": (0.20, f.get("PIR_DEC")),
        "CROWD": (0.15, f.get("PIR_CROWD")),
        "USED": (0.10, f.get("PIR_USED")),
    })


def pv(f: Mapping[str, float | None]) -> float | None:
    return wa({
        "RBV3": (0.35, f.get("RBV3")),
        "RBV6": (0.25, f.get("RBV6")),
        "PROFACC": (0.20, f.get("PROFACC")),
        "GROWACC": (0.20, f.get("GROWACC")),
    })


def market_ignition(f: Mapping[str, float | None]) -> float | None:
    return wa({
        "RSACC": (0.25, f.get("RSACC")),
        "BREAK": (0.20, f.get("BREAK")),
        "PVACC": (0.20, f.get("PVACC")),
        "BREADTH": (0.15, f.get("BREADTH")),
        "VOLCOMP": (0.10, f.get("VOLCOMP")),
        "GAP": (0.10, f.get("GAP")),
    })


def revision_acceleration(f: Mapping[str, float | None]) -> float | None:
    return wa({
        "EPSBreadth": (0.35, f.get("EPS_BREADTH")),
        "EPSMagnitude": (0.25, f.get("EPS_MAGNITUDE")),
        "RevenueBreadth": (0.25, f.get("REVENUE_BREADTH")),
        "TargetAcceleration": (0.15, f.get("TARGET_ACCELERATION")),
    })


def regime_acceleration(f: Mapping[str, float | None]) -> float | None:
    return wa({
        "SectorRSAccel": (0.40, f.get("SECTOR_RS_ACCEL")),
        "ThemeBreadthAccel": (0.35, f.get("THEME_BREADTH_ACCEL")),
        "UnderlyingAssetAccel": (0.25, f.get("UNDERLYING_ASSET_ACCEL")),
    })


def flow(f: Mapping[str, float | None]) -> float | None:
    return wa({
        "DollarVolumeAccel": (0.35, f.get("DOLLAR_VOLUME_ACCEL")),
        "TurnoverAccel": (0.25, f.get("VOLACC")),
        "Accumulation": (0.20, f.get("PVACC")),
        "Positioning": (0.20, f.get("POSITIONING")),
    })


def execution_readiness(f: Mapping[str, float | None], *, horizon15: bool = False) -> float | None:
    prefix = "EXEC15_" if horizon15 else ""
    return wa({
        "CashRunway": (0.30, f.get(prefix + "CASH_RUNWAY") if horizon15 else f.get("CASH_RUNWAY")),
        "FundingReadiness": (0.25, f.get(prefix + "FUNDING_READINESS") if horizon15 else f.get("FUNDING_READINESS")),
        "MilestoneReadiness": (0.20, f.get(prefix + "MILESTONE_READINESS") if horizon15 else f.get("MILESTONE_READINESS")),
        "CapacityReadiness": (0.15, f.get(prefix + "CAPACITY_READINESS") if horizon15 else f.get("CAPACITY_READINESS")),
        "DependencyQuality": (0.10, f.get(prefix + "DEPENDENCY_QUALITY") if horizon15 else f.get("DEPENDENCY_QUALITY")),
    })


def t10(components: Mapping[str, float | None]) -> tuple[float | None, int]:
    legs = {
        "CT": (0.25, components.get("CT")),
        "PV": (0.20, components.get("PV")),
        "MI": (0.15, components.get("MI")),
        "REV": (0.10, components.get("REV")),
        "RA": (0.10, components.get("RA")),
        "FLOW": (0.10, components.get("FLOW")),
        "EXEC": (0.10, components.get("EXEC")),
    }
    present = sum(1 for _, value in legs.values() if value is not None)
    return (wa(legs) if present >= 5 else None), present


def t15(components: Mapping[str, float | None]) -> tuple[float | None, int]:
    legs = {
        "CT15": (0.25, components.get("CT15")),
        "PV": (0.20, components.get("PV")),
        "MI": (0.15, components.get("MI")),
        "REV": (0.10, components.get("REV")),
        "RA": (0.10, components.get("RA")),
        "FLOW": (0.10, components.get("FLOW")),
        "EXEC15": (0.10, components.get("EXEC15")),
    }
    present = sum(1 for _, value in legs.values() if value is not None)
    return (wa(legs) if present >= 5 else None), present


def magnitude(
    *,
    df: float | None,
    mch: float | None,
    etrq_score: float | None,
    rer_score: float | None,
    cmag_score: float | None,
    fcvx_score: float | None,
    hmg: float | None,
    pir_score: float | None,
) -> tuple[float | None, float | None, int]:
    legs = {
        "DF": (0.30, df),
        "MCH": (0.15, mch),
        "ETRQ": (0.15, etrq_score),
        "RER": (0.15, rer_score),
        "CMAG": (0.10, cmag_score),
        "FCVX": (0.05, fcvx_score),
        "HMG": (0.10, hmg),
    }
    present = sum(1 for _, value in legs.values() if value is not None)
    raw = wa(legs) if present >= 5 else None
    if raw is None or pir_score is None:
        return raw, None, present
    return raw, clip(raw - 0.10 * pir_score), present


DESTINATION_KNOTS = (
    (0.20, 0.0),
    (0.35, 25.0),
    (0.50, 50.0),
    (0.75, 75.0),
    (1.00, 100.0),
)


def destination_score(supported_mc_12: float | None, current_mc: float | None, k: float) -> float | None:
    if supported_mc_12 is None or current_mc is None or current_mc <= 0 or k <= 0:
        return None
    ratio = supported_mc_12 / (k * current_mc)
    return piecewise_score(ratio, DESTINATION_KNOTS)


def market_cap_headroom(
    plausible_ceiling_mc: float | None,
    current_mc: float | None,
    k: float,
) -> float | None:
    if plausible_ceiling_mc is None or current_mc is None or current_mc <= 0 or k <= 0:
        return None
    return 100.0 * min(1.0, max(0.0, plausible_ceiling_mc / (k * current_mc)))


def catalyst_time_score(trading_days: int | None) -> float | None:
    if trading_days is None:
        return None
    if trading_days <= 63:
        return 100.0
    if trading_days <= 126:
        return 90.0
    if trading_days <= 189:
        return 75.0
    if trading_days <= 252:
        return 60.0
    if trading_days <= 378:
        return 35.0
    return 10.0


def catalyst_magnitude_score(impact_ratio: float | None) -> float | None:
    if impact_ratio is None:
        return None
    return piecewise_score(impact_ratio, (
        (0.10, 0.0),
        (0.25, 25.0),
        (0.50, 50.0),
        (1.00, 75.0),
        (2.00, 100.0),
    ))


def catalyst_stack_score(count: int | None) -> float | None:
    if count is None:
        return None
    if count <= 0:
        return 0.0
    if count == 1:
        return 40.0
    if count == 2:
        return 70.0
    return 100.0


def asymmetry_score(expected_upside_pct: float | None, expected_downside_pct: float | None) -> float | None:
    if expected_upside_pct is None or expected_downside_pct is None:
        return None
    downside = abs(expected_downside_pct)
    if downside <= 0:
        return None
    return pos_score(expected_upside_pct / downside, 1.0, 5.0)
