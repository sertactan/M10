from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelView:
    model_name: str
    status: str
    score: float | None = None
    route: str | None = None
    destination: str | None = None
    confidence: float | None = None
    risk: str | None = None


@dataclass(frozen=True)
class ComparisonView:
    v12: ModelView
    v14: ModelView
    consensus: str | None = None
    winner: str | None = None
    combined_conviction: str | None = None
