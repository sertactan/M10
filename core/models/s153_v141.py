from __future__ import annotations

from dataclasses import replace
from typing import Mapping

from core.models.s153_v12 import S153V12Model
from core.models.s153_v12_contracts import S153V12Input, S153V12Result
from core.models.s153_v14 import S153V14Model
from core.models.s153_v14_contracts import S153V14Input, S153V14Result
from core.scoring.math import clip, wa
from core.scoring.s153_v12_components import destination_score


V141_FORMULA_VERSION = "S15.3_V1.4.1_CANONICAL_COMPLETION_2026-10-07"


def _v12_input(data: S153V14Input) -> S153V12Input:
    return S153V12Input(
        security_id=data.security_id,
        ticker=data.ticker,
        as_of=data.as_of,
        discovery_factors=data.discovery_factors,
        control_factors=data.control_factors,
        features={k: v for k, v in data.features.items() if not k.startswith("V14_")},
        current_price=data.current_price,
        current_market_cap=data.current_market_cap,
    )


def _route_supported_key(route: str | None) -> str | None:
    if route in {"F10", "I10"}:
        return "SUPPORTED_MC_12_FI"
    if route == "D10":
        return "SUPPORTED_MC_12_D"
    if route == "B10":
        return "SUPPORTED_MC_12_B"
    if route == "R10":
        return "SUPPORTED_MC_12_R"
    return None


def route_purity(v12: S153V12Result) -> float | None:
    primary = v12.primary_route
    if primary is None:
        return None
    p = v12.routes.get(primary)
    if p is None:
        return None
    secondary = v12.secondary_route
    if secondary is None:
        return 100.0
    s = v12.routes.get(secondary)
    if s is None:
        return None
    margin = max(0.0, float(p) - float(s))
    return clip(50.0 + 2.0 * margin)


def route_confidence_features(
    *,
    features: Mapping[str, float | None],
    v12: S153V12Result,
) -> tuple[dict[str, float], tuple[str, ...]]:
    rp = route_purity(v12)
    values = {
        "V14_RC_DC": features.get("DATA_COVERAGE"),
        "V14_RC_EQ": features.get("SOURCE_QUALITY"),
        "V14_RC_RP": rp,
        "V14_RC_ST": features.get("MODEL_FIT"),
        "V14_RC_PIT": features.get("PIT_INTEGRITY"),
    }
    missing = tuple(k for k, v in values.items() if v is None)
    if missing:
        return {}, missing
    return {k: clip(float(v)) for k, v in values.items()}, ()


def _rc(rc_features: Mapping[str, float]) -> float:
    return clip(
        0.25 * rc_features["V14_RC_DC"]
        + 0.25 * rc_features["V14_RC_EQ"]
        + 0.20 * rc_features["V14_RC_RP"]
        + 0.15 * rc_features["V14_RC_ST"]
        + 0.15 * rc_features["V14_RC_PIT"]
    )


def assumption_burden(
    *,
    features: Mapping[str, float | None],
    control_factors: Mapping[str, float | None],
    v12: S153V12Result,
) -> tuple[float | None, dict[str, float | None], tuple[str, ...]]:
    growth_legs = {
        "MCR": (0.35, control_factors.get("MCR")),
        "TAMMC": (0.25, control_factors.get("TAMMC")),
        "GP": (0.20, control_factors.get("GP")),
        "RPS": (0.10, control_factors.get("RPS")),
        "FPS": (0.10, control_factors.get("FPS")),
    }
    growth_present = sum(1 for _, value in growth_legs.values() if value is not None)
    growth_core = (
        control_factors.get("MCR") is not None
        or control_factors.get("TAMMC") is not None
    )
    growth_evidence = wa(growth_legs) if growth_present >= 3 and growth_core else None

    etrq = v12.components.get("ETRQ")
    rer = v12.components.get("RER")
    pir_val = features.get("PIR_VAL")
    viability = v12.components.get("V")
    exec_score = v12.components.get("EXEC")
    t10 = v12.components.get("T10")

    execution_evidence = None
    if exec_score is not None and t10 is not None:
        execution_evidence = 0.60 * float(exec_score) + 0.40 * float(t10)

    stretches: dict[str, float | None] = {
        "V141_GROWTH_STRETCH": None if growth_evidence is None else clip(100.0 - growth_evidence),
        "V141_MARGIN_STRETCH": None if etrq is None else clip(100.0 - float(etrq)),
        "V141_MULTIPLE_STRETCH": (
            None
            if rer is None or pir_val is None
            else clip(0.60 * (100.0 - float(rer)) + 0.40 * float(pir_val))
        ),
        "V141_FUNDING_STRETCH": None if viability is None else clip(100.0 - float(viability)),
        "V141_EXECUTION_STRETCH": (
            None if execution_evidence is None else clip(100.0 - execution_evidence)
        ),
    }
    missing = tuple(k for k, v in stretches.items() if v is None)
    if missing:
        return None, stretches, missing

    ab = clip(
        0.30 * float(stretches["V141_GROWTH_STRETCH"])
        + 0.20 * float(stretches["V141_MARGIN_STRETCH"])
        + 0.20 * float(stretches["V141_MULTIPLE_STRETCH"])
        + 0.15 * float(stretches["V141_FUNDING_STRETCH"])
        + 0.15 * float(stretches["V141_EXECUTION_STRETCH"])
    )
    return ab, stretches, ()


def _q_destination(features: Mapping[str, float | None]) -> float | None:
    return wa({
        "FloatTightness": (0.35, features.get("FLOAT_TIGHTNESS")),
        "ShortStress": (0.25, features.get("SHORT_STRESS")),
        "GammaConvexity": (0.20, features.get("GAMMA_CONVEXITY")),
        "TurnoverAcceleration": (0.20, features.get("TURNOVER_ACCELERATION")),
    })


def _route_df10(
    route: str,
    *,
    features: Mapping[str, float | None],
    current_market_cap: float,
) -> float | None:
    if route == "Q10":
        return _q_destination(features)
    key = _route_supported_key(route)
    if key is None:
        return None
    return destination_score(features.get(key), current_market_cap, 10.0)


def generate_v141_features(
    *,
    data: S153V14Input,
    v12: S153V12Result,
) -> tuple[dict[str, float], dict[str, float | None], tuple[str, ...], str | None]:
    if v12.score is None:
        return {}, {}, ("V1.2 READY",), None
    if data.current_market_cap is None or float(data.current_market_cap) <= 0:
        return {}, {}, ("RAW_CURRENT_MARKET_CAP>0",), None
    if v12.primary_route == "Q10":
        return {}, {}, ("primary Q10 has no canonical SupportedMC scenario construction",), "INCONCLUSIVE_V1_4_1_Q_ROUTE"

    rc_features, rc_missing = route_confidence_features(features=data.features, v12=v12)
    if rc_missing:
        return {}, {}, rc_missing, None
    rc = _rc(rc_features)

    ab, stretches, ab_missing = assumption_burden(
        features=data.features,
        control_factors=data.control_factors,
        v12=v12,
    )
    if ab is None:
        return {}, stretches, ab_missing, None

    supported_key = _route_supported_key(v12.primary_route)
    supported = data.features.get(supported_key) if supported_key else None
    if supported is None or float(supported) <= 0:
        return {}, stretches, (supported_key or "primary route SupportedMC",), None

    ceiling = data.features.get("PLAUSIBLE_CEILING_MC")
    base = float(supported)
    if ceiling is not None and float(ceiling) > 0:
        base = min(base, float(ceiling))
    if base <= 0:
        return {}, stretches, ("V14_MC_BASE>0",), None

    width_pct = clip(15.0 + 35.0 * (100.0 - rc) / 100.0, 15.0, 50.0)
    width = width_pct / 100.0
    mc_bear = base * (1.0 - width)
    mc_bull = base * (1.0 + width)
    if ceiling is not None and float(ceiling) > 0:
        mc_bull = min(mc_bull, float(ceiling))

    current_mc = float(data.current_market_cap)
    df_b = destination_score(mc_bear, current_mc, 10.0)
    df_m = destination_score(base, current_mc, 10.0)
    df_u = destination_score(mc_bull, current_mc, 10.0)
    if any(v is None for v in (df_b, df_m, df_u)):
        return {}, stretches, ("scenario destination factors",), None

    route_gap = 0.0
    if v12.secondary_route is not None:
        primary_df = _route_df10(
            v12.primary_route,
            features=data.features,
            current_market_cap=current_mc,
        )
        secondary_df = _route_df10(
            v12.secondary_route,
            features=data.features,
            current_market_cap=current_mc,
        )
        if primary_df is None or secondary_df is None:
            return {}, stretches, ("V14_ROUTE_GAP",), None
        route_gap = abs(float(primary_df) - float(secondary_df))

    generated = {
        "V14_DF_B": float(df_b),
        "V14_DF_M": float(df_m),
        "V14_DF_U": float(df_u),
        "V14_MC_BEAR": mc_bear,
        "V14_MC_BASE": base,
        "V14_MC_BULL": mc_bull,
        **rc_features,
        "V14_AB": ab,
        "V14_ROUTE_GAP": clip(route_gap),
    }
    diagnostics: dict[str, float | None] = {
        **stretches,
        "V141_ROUTE_CONFIDENCE": rc,
        "V141_SCENARIO_WIDTH_PCT": width_pct,
        "V141_SUPPORTED_MC_PRIMARY": float(supported),
        "V141_PLAUSIBLE_CEILING_MC": (
            float(ceiling) if ceiling is not None and float(ceiling) > 0 else None
        ),
    }
    return generated, diagnostics, (), None


class S153V141Model:
    model_id = "S15.3_V1.4.1"
    canonical_formula_version = V141_FORMULA_VERSION

    def __init__(self) -> None:
        self.v12_model = S153V12Model()
        self.v14_model = S153V14Model()

    def analyze(self, data: S153V14Input) -> S153V14Result:
        if data.as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")

        v12 = self.v12_model.analyze(_v12_input(data))
        generated, diagnostics, missing, special_status = generate_v141_features(
            data=data,
            v12=v12,
        )
        if missing:
            return S153V14Result(
                security_id=data.security_id,
                ticker=data.ticker,
                as_of=data.as_of,
                score=None,
                status=special_status or "INCONCLUSIVE_V1_4_1_INPUTS",
                primary_route=v12.primary_route,
                secondary_route=v12.secondary_route,
                confidence=v12.confidence,
                components={
                    **v12.components,
                    **diagnostics,
                    "M10_D": v12.components.get("M10"),
                },
                flags={"PRECISION_CONFIRMED": False},
                missing_requirements=tuple(dict.fromkeys(missing)),
            )

        enriched = replace(data, features={**data.features, **generated})
        result = self.v14_model.analyze(enriched)
        return replace(
            result,
            components={
                **result.components,
                **diagnostics,
                **generated,
                "S15.3_V1.4.1": result.score,
            },
        )
