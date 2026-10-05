from __future__ import annotations

from pathlib import Path

from app.bootstrap import AppContainer
from core.scanner.production import CanonicalDualModelScorer
from data.repositories.model_feature_repository import ModelFeatureRepository


class WorkerLocalCanonicalScorer:
    """One canonical scorer and SQLite connection owned by one worker thread."""

    def __init__(self, root: Path) -> None:
        self.app = AppContainer(root)
        self.app.initialize()
        self.scorer = CanonicalDualModelScorer(ModelFeatureRepository(self.app.sqlite))

    def score(self, candidate, as_of):
        return self.scorer.score(candidate, as_of)

    def close(self) -> None:
        self.app.close()
