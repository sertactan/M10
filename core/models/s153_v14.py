from __future__ import annotations

from core.models.s153_v12 import S153V12Model
from core.models.s153_v12_contracts import S153V12Input
from core.models.s153_v14_contracts import S153V14Input, S153V14Result
from core.scoring.math import clip
from core.scoring.s153_v14_dual import (
    assumption_burden,
    confirmation_bonus,
    confirmation_gap_closure,
    destination_route_acceleration,
    destination_uncertainty,
    disagreement_penalty,
    early_asymmetric_score,
    early_boost,
    early_stall_penalty,
    m10_confirmation,
    progress_gate,
    robust_destination,
    route_blend_alpha,
    route_confidence,
    route_disagreement,
)


class V14CanonicalSpecificationMissing(RuntimeError):
    """Retained for compatibility with callers that import the old Phase-5 gate."""


class S153V14Model:
    model_id = "S15.3_V1.4"
    canonical_formula_version = "S153_V1.4_DUAL_MAGNITUDE_2026-10-05"

    def __init__(self, binding=None, *, v12_model: S153V12Model | None = None) -> None:
        # The recovered/approved V1.4 math is now executable in code.
        # binding is accepted only for backwards compatibility with the former gate.
        self.binding = binding
        self.v12_model = v12_model or S153V12Model()

    @staticmethod
    def _v12_input(data: S153V14Input) -> S153V12Input:
        return S153V12Input(
            security_id=data.security_id,
            ticker=data.ticker,
            as_of=data.as_of,
            discovery_factors=data.discovery_factors,
            control_factors=data.control_factors,
            features=data.features,
            current_price=data.current_price,
            current_market_cap=data.current_market_cap,
        )

    def analyze(self, data: S153V14Input) -> S153V14Result:
        if data.as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")

        v12 = self.v12_model.analyze(self._v12_input(data))
        f = dict(data.features)
        f["MI"] = v12.components.get("MI")

        m10_d = v12.components.get("M10")
        t10 = v12.components.get("T10")
        base_df10 = v12.components.get("DF10")
        rc = route_confidence(f)
        alpha = route_blend_alpha(rc)

        rdf10, df10_c = robust_destination(
            base_df10=base_df10,
            df_bear=f.get("V14_DF_BEAR"),
            df_base=f.get("V14_DF_BASE"),
            df_bull=f.get("V14_DF_BULL"),
            alpha=alpha,
        )
        du, dup = destination_uncertainty(
            mc_bear=f.get("V14_MC_BEAR"),
            mc_base=f.get("V14_MC_BASE"),
            mc_bull=f.get("V14_MC_BULL"),
            explicit_du=f.get("V14_DU"),
        )
        ab, abp = assumption_burden(f)
        route_gap, rdp = route_disagreement(f)

        m10_c_raw, m10_c, m10_c_legs = m10_confirmation(
            df10_v13=df10_c,
            mch10=v12.components.get("MCH10"),
            etrq=v12.components.get("ETRQ"),
            rer=v12.components.get("RER"),
            cmag=v12.components.get("CMAG"),
            fcvx=v12.components.get("FCVX"),
            hmg10=v12.components.get("HMG10"),
            pir=v12.components.get("PIR"),
            dup=dup,
            abp=abp,
            rdp=rdp,
        )

        missing: list[str] = []
        if v12.score is None:
            missing.append("S15.3_V1.2")
        if m10_d is None:
            missing.append("M10_D")
        if rc is None:
            missing.append("V1.3_RC")
        if df10_c is None:
            missing.append("V1.3_DF10")
        if dup is None:
            missing.append("V1.3_DUP")
        if abp is None:
            missing.append("V1.3_ABP")
        if rdp is None:
            missing.append("V1.3_RDP")
        if m10_c is None or m10_c_legs < 5:
            missing.append("M10_C>=5/7")
        if t10 is None:
            missing.append("T10")

        dmg = (
            float(m10_d) - float(m10_c)
            if m10_d is not None and m10_c is not None
            else None
        )
        cb = confirmation_bonus(m10_c, dmg)
        dp = disagreement_penalty(dmg)

        core_v14 = None
        if not missing and cb is not None and dp is not None:
            core_v14 = clip(float(v12.score) + float(cb) - float(dp))

        early_active = bool(
            v12.score is not None
            and v12.score >= 65.0
            and m10_d is not None
            and m10_d >= 65.0
            and m10_c is not None
            and (m10_c < 70.0 or (dmg is not None and dmg > 10.0))
        )

        cgc = None
        dra = None
        ea10 = None
        ea_route = None
        ea_parts: dict[str, float | None] = {
            "CA10": None,
            "AA10": None,
            "SPIN_ACCEL": None,
        }
        progress_pass = False
        progress_count = 0
        eab = 0.0
        esp = 0.0

        if early_active and core_v14 is not None:
            cgc = confirmation_gap_closure(
                dmg_now=dmg,
                dmg_3m_ago=f.get("V14_DMG_3M_AGO"),
                explicit_cgc=f.get("V14_CGC"),
            )
            dra = destination_route_acceleration(f)
            ea10, ea_route, ea_parts = early_asymmetric_score(
                f,
                dra=dra,
                cgc=cgc,
            )
            progress_pass, progress_count = progress_gate(f, dra=dra, cgc=cgc)
            if ea10 is None:
                missing.append("EA10")
            else:
                eab = float(early_boost(ea10, progress_pass) or 0.0)
                esp = float(early_stall_penalty(ea10) or 0.0)

        final_score = None
        if core_v14 is not None and not (early_active and ea10 is None):
            final_score = clip(core_v14 + eab - esp)
            # Latest recovered EA rule: confirmation below 70 cannot enter 80+.
            if m10_c is not None and m10_c < 70.0:
                final_score = min(final_score, 79.0)

        precision = bool(
            final_score is not None
            and final_score >= 80.0
            and m10_d is not None and m10_d >= 70.0
            and m10_c is not None and m10_c >= 70.0
            and t10 is not None and t10 >= 70.0
            and base_df10 is not None and base_df10 >= 60.0
            and v12.components.get("XR") is not None
            and v12.components["XR"] >= 99.0
            and v12.components.get("HMG10") is not None
            and bool(v12.route_gate)
            and v12.confidence is not None
            and v12.confidence >= 70.0
        )
        strong = bool(
            final_score is not None
            and final_score >= 75.0
            and m10_d is not None and m10_d >= 65.0
            and m10_c is not None and m10_c >= 65.0
            and t10 is not None and t10 >= 65.0
            and bool(v12.route_gate)
        )
        discovery = bool(final_score is not None and final_score >= 65.0)

        if missing:
            status = "INCONCLUSIVE"
        elif precision:
            status = "PRECISION_CONFIRMED_12M_10X"
        elif early_active and ea10 is not None and ea10 >= 75.0 and progress_pass:
            status = "EARLY_ACCELERATING_10X"
        elif early_active and ea10 is not None and ea10 >= 60.0:
            status = "EARLY_ASYMMETRIC_WATCH"
        elif early_active:
            status = "EARLY_STALLED"
        elif final_score is not None and final_score >= 80.0:
            status = "HIGH_SCORE_NOT_CONFIRMED"
        elif strong:
            status = "STRONG_10X_WATCH"
        elif discovery:
            status = "10X_DISCOVERY"
        else:
            status = "NO_CANONICAL_GATE_STATUS"

        components = dict(v12.components)
        components.update({
            "S15.3_V1.2": v12.score,
            "M10_D": m10_d,
            "RC": rc,
            "ALPHA": alpha,
            "RDF10": rdf10,
            "DF10_C": df10_c,
            "DU": du,
            "DUP": dup,
            "AB": ab,
            "ABP": abp,
            "ROUTE_GAP": route_gap,
            "RDP": rdp,
            "M10_C_RAW": m10_c_raw,
            "M10_C": m10_c,
            "DMG": dmg,
            "CB": cb,
            "DP": dp,
            "S15.3_V1.4_CORE": core_v14,
            "CGC": cgc,
            "DRA": dra,
            "EA10": ea10,
            "EAB": eab,
            "ESP": esp,
            "S15.3_V1.4": final_score,
            **ea_parts,
        })
        flags = {
            "PRECISION_CONFIRMED": precision,
            "STRONG_WATCH": strong,
            "DISCOVERY": discovery,
            "EARLY_ASYMMETRIC": early_active,
            "PROGRESS_GATE": progress_pass,
            "M10_CONFIRMATION_GE_70": bool(m10_c is not None and m10_c >= 70.0),
        }

        return S153V14Result(
            security_id=data.security_id,
            ticker=data.ticker,
            as_of=data.as_of,
            score=final_score,
            status=status,
            primary_route=v12.primary_route,
            secondary_route=v12.secondary_route,
            primary_magnitude=None,
            extreme_magnitude=None,
            acceleration_score=ea10,
            large_winner_probability=None,
            risk_adjusted_conviction=None,
            confidence=v12.confidence,
            probability_buckets={},
            components=components,
            flags=flags,
            missing_requirements=tuple(dict.fromkeys(missing)),
        )
