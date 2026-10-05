from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

from core.config.models import ModelConfig


class ModelNotImplemented(RuntimeError):
    pass


@dataclass(frozen=True)
class ModelInput:
    security_id: str
    ticker: str
    as_of: datetime
    factors: Mapping[str, float | None]


@dataclass(frozen=True)
class ModelOutput:
    score: float | None
    route: str | None
    destination: str | None
    prediction: str
    status: str


class S153ModelBase:
    def __init__(self, config: ModelConfig) -> None:
        self.config = config

    def analyze(self, data: ModelInput) -> ModelOutput:
        if not self.config.enabled:
            raise ModelNotImplemented(
                f"{self.config.model_id} is disabled: {self.config.status}"
            )
        raise ModelNotImplemented(
            f"Canonical engine for {self.config.model_id} is not implemented yet"
        )
