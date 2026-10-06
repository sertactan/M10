from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScoreBucket:
    name: str
    minimum: float
    maximum: float

    def contains(self, value: float) -> bool:
        return self.minimum <= value < self.maximum


@dataclass(frozen=True)
class ScoreBucketStats:
    name: str
    count: int
    average_score: float | None
    average_fm252: float | None
    true_10x: int
    precision_confirmed: int


@dataclass(frozen=True)
class RoutePerformance:
    route: str
    count: int
    average_score: float | None
    average_return_12m: float | None


@dataclass(frozen=True)
class FalsePositiveBreakdown:
    model_version: str
    true_positive: int
    near_miss_false_positive: int
    magnitude_false_positive: int
    strong_winner_false_positive: int
    hard_false_positive: int


@dataclass(frozen=True)
class ModelComparison:
    model_a: str
    model_b: str
    paired_observations: int
    average_score_a: float | None
    average_score_b: float | None
    average_score_difference_b_minus_a: float | None
    precision_confirmed_a: int
    precision_confirmed_b: int
    precision_agreement: int
    precision_disagreement: int
    true_10x_observations: int
