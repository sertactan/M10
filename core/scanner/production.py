from __future__ import annotations

from datetime import datetime
from typing import Protocol

from core.features.s153_v12_input_loader import S153V12InputLoader
from core.features.s153_v14_input_loader import S153V14InputLoader
from core.models.s153_v12 import S153V12Model
from core.models.s153_v14 import S153V14Model
from core.scanner.contracts import ScanCandidate
from data.repositories.model_feature_repository import ModelFeatureRepository
from data.repositories.security_repository import SecurityRepository


class ScannerDependencyError(RuntimeError):
    pass


class CandidateSource(Protocol):
    def current(self) -> list[ScanCandidate]: ...
    def historical(self, as_of: datetime) -> list[ScanCandidate]: ...


class SecurityScorer(Protocol):
    def score(self, candidate: ScanCandidate, as_of: datetime): ...


class RepositoryCandidateSource:
    def __init__(self, repository: SecurityRepository) -> None:
        self.repository = repository

    @staticmethod
    def _candidate(row: dict) -> ScanCandidate:
        return ScanCandidate(
            security_id=str(row["security_id"]),
            ticker=str(row["ticker"]),
            exchange=str(row["exchange"]),
            name=str(row.get("name") or ""),
            active=bool(row.get("active", 1)),
            delisted_date=row.get("delisted_date"),
        )

    def current(self) -> list[ScanCandidate]:
        return [self._candidate(row) for row in self.repository.current_us_common_stocks()]

    def historical(self, as_of: datetime) -> list[ScanCandidate]:
        if as_of.tzinfo is None:
            raise ValueError("historical scan as_of must be timezone-aware")
        rows = self.repository.universe_as_of(as_of.date())
        if not rows:
            raise ScannerDependencyError(
                "No canonical historical universe snapshot exists for the requested date"
            )
        return [self._candidate(row) for row in rows]


class CanonicalDualModelScorer:
    """Production scoring adapter. No fallback or synthetic model output is allowed."""

    def __init__(
        self,
        feature_repository: ModelFeatureRepository,
        *,
        v12_model: S153V12Model | None = None,
        v14_model: S153V14Model | None = None,
    ) -> None:
        self.v12_loader = S153V12InputLoader(feature_repository)
        self.v14_loader = S153V14InputLoader(feature_repository)
        self.v12_model = v12_model or S153V12Model()
        self.v14_model = v14_model or S153V14Model()

    def score(self, candidate: ScanCandidate, as_of: datetime):
        if as_of.tzinfo is None:
            raise ValueError("scan as_of must be timezone-aware")
        v12_input = self.v12_loader.load(
            security_id=candidate.security_id,
            ticker=candidate.ticker,
            as_of=as_of,
        )
        v14_input = self.v14_loader.load(
            security_id=candidate.security_id,
            ticker=candidate.ticker,
            as_of=as_of,
        )

        # Deliberately fail closed if either canonical model is not executable.
        v12 = self.v12_model.analyze(v12_input)
        v14 = self.v14_model.analyze(v14_input)
        return v12, v14
