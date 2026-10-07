from __future__ import annotations

from datetime import datetime

from core.backtest.contracts import ForwardOutcome
from core.historical.wf4_vector_policy import (
    VECTOR_VERSION,
    broad_vector,
    magnitude5_vector,
    magnitude10_vector,
)
from core.models.s153_v12_contracts import S153V12Result
from data.repositories.s153_historical_control_repository import S153HistoricalControlRepository


class WF4HistoricalObservationBuilder:
    """Persist historical vectors only after a forward label is READY.

    The label is stored separately from the feature vector and becomes cohort-
    eligible only at label_available_at.
    """

    def __init__(self, repository: S153HistoricalControlRepository) -> None:
        self.repository=repository

    def save_ready(
        self,
        *,
        observation_id: str,
        result: S153V12Result,
        outcome: ForwardOutcome,
        label_available_at: datetime,
        source_run_id: str | None = None,
    ) -> bool:
        if outcome.outcome_status != "READY":
            return False
        if outcome.fm252 is None or outcome.outcome_class is None:
            return False
        if label_available_at.tzinfo is None:
            raise ValueError("label_available_at must be timezone-aware")

        self.repository.save(
            observation_id=observation_id,
            security_id=result.security_id,
            as_of_date=result.as_of.date().isoformat(),
            primary_route=result.primary_route,
            feature_vector=broad_vector(
                result.components,
                primary_route=result.primary_route,
            ),
            magnitude_vector=magnitude10_vector(
                result.components,
                primary_route=result.primary_route,
            ),
            magnitude5_vector=magnitude5_vector(
                result.components,
                primary_route=result.primary_route,
            ),
            fm252=float(outcome.fm252),
            outcome_class=str(outcome.outcome_class),
            label_available_at=label_available_at,
            vector_version=VECTOR_VERSION,
            source_run_id=source_run_id,
        )
        return True
