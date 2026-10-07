from __future__ import annotations

from datetime import datetime

from core.historical.wf4_controls import WF4HistoricalControlEngine
from core.historical.wf4_policy import hmg5, xr_score
from core.historical.wf4_vector_policy import (
    VECTOR_VERSION,
    broad_vector,
    magnitude5_vector,
    magnitude10_vector,
)
from data.repositories.model_feature_repository import ModelFeatureRepository
from data.repositories.s153_historical_control_repository import S153HistoricalControlRepository


class WF4HistoricalFeatureMaterializer:
    VERSION="wf4-historical-features-v2-wf6-leakage-v1"

    def __init__(
        self,
        controls: S153HistoricalControlRepository,
        features: ModelFeatureRepository,
    ) -> None:
        self.controls=controls
        self.features=features
        self.engine=WF4HistoricalControlEngine(controls)

    def materialize(
        self,
        *,
        security_id: str,
        as_of: datetime,
        primary_route: str | None,
        market_cap_bucket: str | None,
        components: dict[str,float|None],
        same_month_rows: list[dict],
    ) -> dict[str,str]:
        broad=broad_vector(components,primary_route=primary_route)
        magnitude5=magnitude5_vector(components,primary_route=primary_route)
        magnitude10=magnitude10_vector(components,primary_route=primary_route)
        hist=self.engine.compute(
            as_of=as_of,
            broad_target=broad,
            magnitude10_target=magnitude10,
            target_security_id=security_id,
        )

        eligible=self.controls.eligible_before(
            as_of,
            vector_version=VECTOR_VERSION,
            exclude_security_id=security_id,
        )
        winner5=[r for r in eligible if float(r["fm252"]) >= 5.0]
        near5=[r for r in eligible if 3.0 <= float(r["fm252"]) < 5.0]
        hard=[r for r in eligible if float(r["fm252"]) < 3.0]

        from core.historical.s153_controls import cohort_similarity
        # Stored WF4 V1 rows carry the 10X magnitude vector. HMG5 requires
        # a dedicated DF5/MCH5 vector in newly materialized observations;
        # rows lacking it are not silently reused.
        winner5_vectors=[r.get("magnitude5_vector") for r in winner5 if r.get("magnitude5_vector")]
        near5_vectors=[r.get("magnitude5_vector") for r in near5 if r.get("magnitude5_vector")]
        hard5_vectors=[r.get("magnitude5_vector") for r in hard if r.get("magnitude5_vector")]
        w5=cohort_similarity(magnitude5,winner5_vectors)
        n5=cohort_similarity(magnitude5,near5_vectors)
        h5=cohort_similarity(magnitude5,hard5_vectors)
        hmg5_score=hmg5(w5,n5,h5)

        xr=xr_score(
            rb=components.get("RB"),
            route=primary_route,
            market_cap_bucket=market_cap_bucket,
            exact_rows=same_month_rows,
            route_rows=same_month_rows,
        )

        values={
            "WINNER_SIM":hist.get("WINNER_SIM"),
            "CONTROL_SIM":hist.get("CONTROL_SIM"),
            "H10":hist.get("H10"),
            "HMG10":hist.get("HMG10"),
            "HMG5":hmg5_score,
            "XR":xr.score,
        }
        written={}
        for key,value in values.items():
            if value is None:
                continue
            written[key]=self.features.save_feature(
                security_id=security_id,
                feature_key=key,
                value=float(value),
                feature_as_of=as_of,
                available_at=as_of,
                source_phase="HISTORICAL_CONTROLS",
                source_ref=f"WF4:{security_id}:{as_of.isoformat()}",
                quality_status=(
                    "CANONICAL_DERIVED"
                    if key != "XR" or xr.status=="NORMAL"
                    else "CANONICAL_DERIVED_LOW_CONFIDENCE"
                ),
                computation_version=self.VERSION,
                evidence={
                    "vector_version":VECTOR_VERSION,
                    "leakage_policy":"WF6_LEAKAGE_POLICY_V1_2026-10-07",
                    "target_security_excluded":True,
                    "true10_n":hist.get("WF4_TRUE10_N"),
                    "near10_n":hist.get("WF4_NEAR_MISS_N"),
                    "hard_n":hist.get("WF4_HARD_N"),
                    "winner5_n":len(winner5),
                    "near5_n":len(near5),
                    "xr_peer_n":xr.peer_n,
                    "xr_scope":xr.scope,
                    "xr_status":xr.status,
                },
            )
        return written
