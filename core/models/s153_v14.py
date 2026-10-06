from __future__ import annotations

from core.models.s153_v12 import S153V12Model
from core.models.s153_v12_contracts import S153V12Input
from core.models.s153_v14_contracts import S153V14Input, S153V14Result
from core.models.s153_v14_recovered import (
    RECOVERED_FORMULA_VERSION,
    calculate_recovered_v14,
    missing_v13_features,
)
from core.models.s153_v14_spec_manifest import V14SpecificationBinding


class V14CanonicalSpecificationMissing(RuntimeError):
    """Retained for compatibility with older callers of the fail-closed scaffold."""


class S153V14Model:
    model_id = "S15.3_V1.4"
    canonical_formula_version = RECOVERED_FORMULA_VERSION

    def __init__(self, binding: V14SpecificationBinding | None = None) -> None:
        # Binding is retained as reproducibility metadata. The recovered formulas
        # are now embedded and locked by repository Golden tests.
        self.binding = binding or V14SpecificationBinding()
        self.v12_model = S153V12Model()

    @staticmethod
    def _v12_input(data: S153V14Input) -> S153V12Input:
        # V14-only raw/scenario inputs are not passed to the V1.2 validator.
        v12_features = {
            key: value
            for key, value in data.features.items()
            if not key.startswith("V14_")
        }
        return S153V12Input(
            security_id=data.security_id,
            ticker=data.ticker,
            as_of=data.as_of,
            discovery_factors=data.discovery_factors,
            control_factors=data.control_factors,
            features=v12_features,
            current_price=data.current_price,
            current_market_cap=data.current_market_cap,
        )

    def analyze(self, data: S153V14Input) -> S153V14Result:
        if data.as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")

        v12 = self.v12_model.analyze(self._v12_input(data))
        required_components = (
            "S15.3",
            "M10",
            "DF10",
            "MCH10",
            "ETRQ",
            "RER",
            "CMAG",
            "FCVX",
            "HMG10",
            "PIR",
            "T10",
        )
        missing = [
            name
            for name in required_components
            if v12.components.get(name) is None
        ]
        missing.extend(missing_v13_features(data.features))
        if missing:
            return S153V14Result(
                security_id=data.security_id,
                ticker=data.ticker,
                as_of=data.as_of,
                score=None,
                status="INCONCLUSIVE_V1_4_INPUTS",
                primary_route=v12.primary_route,
                secondary_route=v12.secondary_route,
                confidence=v12.confidence,
                components={
                    **v12.components,
                    "M10_D": v12.components.get("M10"),
                },
                flags={"PRECISION_CONFIRMED": False},
                missing_requirements=tuple(dict.fromkeys(missing)),
            )

        try:
            recovered = calculate_recovered_v14(
                features=data.features,
                v12_score=float(v12.score),
                m10_d=float(v12.components["M10"]),
                base_df10=float(v12.components["DF10"]),
                mch10=float(v12.components["MCH10"]),
                etrq=float(v12.components["ETRQ"]),
                rer=float(v12.components["RER"]),
                cmag=float(v12.components["CMAG"]),
                fcvx=float(v12.components["FCVX"]),
                hmg10=float(v12.components["HMG10"]),
                pir=float(v12.components["PIR"]),
                mi=(
                    float(v12.components["MI"])
                    if v12.components.get("MI") is not None
                    else None
                ),
            )
        except ValueError as exc:
            return S153V14Result(
                security_id=data.security_id,
                ticker=data.ticker,
                as_of=data.as_of,
                score=None,
                status="INCONCLUSIVE_V1_4_INPUTS",
                primary_route=v12.primary_route,
                secondary_route=v12.secondary_route,
                confidence=v12.confidence,
                components={
                    **v12.components,
                    "M10_D": v12.components.get("M10"),
                },
                flags={"PRECISION_CONFIRMED": False},
                missing_requirements=(str(exc),),
            )

        t10 = float(v12.components["T10"])
        xr = v12.components.get("XR")
        hmg10 = v12.components.get("HMG10")
        confidence = v12.confidence

        precision = bool(
            not recovered.early_asymmetric
            and recovered.final_v14_score >= 80
            and recovered.m10_d >= 70
            and recovered.m10_c >= 70
            and t10 >= 70
            and recovered.df10_confirmation >= 60
            and xr is not None and float(xr) >= 99
            and hmg10 is not None
            and v12.route_gate
            and confidence is not None and confidence >= 70
        )
        strong = bool(
            not recovered.early_asymmetric
            and recovered.final_v14_score >= 75
            and recovered.m10_d >= 65
            and recovered.m10_c >= 65
            and t10 >= 65
        )
        discovery = recovered.final_v14_score >= 65

        if precision:
            status = "PRECISION_CONFIRMED_12M_10X"
        elif recovered.early_asymmetric:
            status = recovered.ea_label or "EARLY_ASYMMETRIC"
        elif recovered.final_v14_score >= 80:
            status = "HIGH_SCORE_NOT_CONFIRMED"
        elif strong:
            status = "STRONG_10X_WATCH"
        elif discovery:
            status = "10X_DISCOVERY"
        else:
            status = "NO_CANONICAL_GATE_STATUS"

        components = {
            **v12.components,
            "M10_D": recovered.m10_d,
            "M10_C": recovered.m10_c,
            "M10_C_RAW": recovered.m10_c_raw,
            "DMG": recovered.dmg,
            "RDF10": recovered.rdf10,
            "ROUTE_CONFIDENCE_V13": recovered.route_confidence,
            "ALPHA_V13": recovered.alpha,
            "DF10_C": recovered.df10_confirmation,
            "DU": recovered.du,
            "DUP": recovered.dup,
            "ABP": recovered.abp,
            "RDP": recovered.rdp,
            "CB": recovered.cb,
            "DP": recovered.dp,
            "S15.3_V1.4_BASE": recovered.base_v14_score,
            "EA10": recovered.ea10,
            "CGC": recovered.cgc,
            "EAB": recovered.eab,
            "ESP": recovered.esp,
            "S15.3_V1.4": recovered.final_v14_score,
        }
        flags = {
            **v12.flags,
            "EARLY_ASYMMETRIC": recovered.early_asymmetric,
            "EA_PROGRESS_GATE": bool(recovered.progress_gate),
            "PRECISION_CONFIRMED": precision,
            "STRONG_WATCH": strong,
            "DISCOVERY": discovery,
        }
        return S153V14Result(
            security_id=data.security_id,
            ticker=data.ticker,
            as_of=data.as_of,
            score=recovered.final_v14_score,
            status=status,
            primary_route=v12.primary_route,
            secondary_route=v12.secondary_route,
            acceleration_score=recovered.ea10,
            large_winner_probability=None,
            risk_adjusted_conviction=None,
            confidence=confidence,
            probability_buckets={},
            components=components,
            flags=flags,
            missing_requirements=(),
        )
