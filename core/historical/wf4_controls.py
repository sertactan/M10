from __future__ import annotations

from datetime import datetime

from core.historical.s153_controls import cohort_similarity, h10, hmg10
from core.historical.wf4_vector_policy import VECTOR_VERSION
from data.repositories.s153_historical_control_repository import S153HistoricalControlRepository


class WF4HistoricalControlEngine:
    """Materialize leakage-safe H10/HMG10 from labels available before target as_of."""

    def __init__(self, repository: S153HistoricalControlRepository) -> None:
        self.repository=repository

    def compute(
        self,
        *,
        as_of: datetime,
        broad_target: dict[str,float|None],
        magnitude10_target: dict[str,float|None],
    ) -> dict[str,float|None]:
        rows=self.repository.eligible_before(as_of,vector_version=VECTOR_VERSION)

        true10=[row for row in rows if row["outcome_class"]=="TRUE_10X"]
        near=[row for row in rows if row["outcome_class"]=="NEAR_MISS_10X"]
        hard=[row for row in rows if float(row["fm252"]) < 3.0]

        winner_b=cohort_similarity(broad_target,[r["feature_vector"] for r in true10])
        near_b=cohort_similarity(broad_target,[r["feature_vector"] for r in near])
        hard_b=cohort_similarity(broad_target,[r["feature_vector"] for r in hard])

        winner_m=cohort_similarity(magnitude10_target,[r["magnitude_vector"] for r in true10])
        near_m=cohort_similarity(magnitude10_target,[r["magnitude_vector"] for r in near])
        hard_m=cohort_similarity(magnitude10_target,[r["magnitude_vector"] for r in hard])

        return {
            "WINNER_SIM": winner_b,
            "CONTROL_SIM": hard_b,
            "H10": h10(winner_b,near_b,hard_b),
            "HMG10": hmg10(winner_m,near_m,hard_m),
            "WF4_TRUE10_N": float(len(true10)),
            "WF4_NEAR_MISS_N": float(len(near)),
            "WF4_HARD_N": float(len(hard)),
        }
