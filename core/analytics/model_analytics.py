from __future__ import annotations

from collections import defaultdict
from statistics import fmean

from core.analytics.contracts import (
    FalsePositiveBreakdown,
    ModelComparison,
    RoutePerformance,
    ScoreBucket,
    ScoreBucketStats,
)
from core.backtest.contracts import ForwardOutcome
from core.backtest.metrics import prediction_error_class
from data.database.sqlite_store import SQLiteStore


class AnalyticsInputError(ValueError):
    pass


class ModelAnalytics:
    """Analytics over persisted model/backtest evidence only.

    This class does not invent score-bucket thresholds. Callers must provide
    explicit bucket definitions. False-positive classes reuse the canonical
    Phase 6 prediction_error_class implementation.
    """

    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    @staticmethod
    def _validate_buckets(buckets: list[ScoreBucket]) -> None:
        if not buckets:
            raise AnalyticsInputError("At least one explicit score bucket is required")
        ordered = sorted(buckets, key=lambda b: (b.minimum, b.maximum, b.name))
        for bucket in ordered:
            if bucket.maximum <= bucket.minimum:
                raise AnalyticsInputError(
                    f"Invalid score bucket {bucket.name}: maximum must exceed minimum"
                )
        for left, right in zip(ordered, ordered[1:]):
            if left.maximum > right.minimum:
                raise AnalyticsInputError(
                    f"Score buckets overlap: {left.name} and {right.name}"
                )

    def score_bucket_stats(
        self,
        *,
        model_version: str,
        buckets: list[ScoreBucket],
    ) -> list[ScoreBucketStats]:
        self._validate_buckets(buckets)
        rows = self.store.connection.execute(
            """
            SELECT p.score,p.precision_confirmed,o.fm252
            FROM backtest_predictions p
            JOIN forward_outcomes o ON o.observation_id=p.observation_id
            WHERE p.model_version=?
              AND p.status='READY'
              AND o.outcome_status='READY'
              AND p.score IS NOT NULL
              AND o.fm252 IS NOT NULL
            """,
            (model_version,),
        ).fetchall()

        output: list[ScoreBucketStats] = []
        for bucket in buckets:
            selected = [
                row for row in rows if bucket.contains(float(row["score"]))
            ]
            scores = [float(row["score"]) for row in selected]
            fm252 = [float(row["fm252"]) for row in selected]
            output.append(
                ScoreBucketStats(
                    name=bucket.name,
                    count=len(selected),
                    average_score=fmean(scores) if scores else None,
                    average_fm252=fmean(fm252) if fm252 else None,
                    true_10x=sum(1 for value in fm252 if value >= 10.0),
                    precision_confirmed=sum(
                        1 for row in selected if bool(row["precision_confirmed"])
                    ),
                )
            )
        return output

    def false_positive_breakdown(
        self,
        *,
        model_version: str,
    ) -> FalsePositiveBreakdown:
        rows = self.store.connection.execute(
            """
            SELECT p.precision_confirmed,o.*
            FROM backtest_predictions p
            JOIN forward_outcomes o ON o.observation_id=p.observation_id
            WHERE p.model_version=?
              AND p.status='READY'
              AND o.outcome_status='READY'
            """,
            (model_version,),
        ).fetchall()

        counts = defaultdict(int)
        for row in rows:
            outcome = ForwardOutcome(
                security_id=row["security_id"],
                as_of_date_requested=__import__("datetime").date.fromisoformat(
                    row["as_of_date_requested"]
                ),
                anchor_session=(
                    __import__("datetime").date.fromisoformat(row["anchor_session"])
                    if row["anchor_session"] else None
                ),
                anchor_lag_calendar_days=row["anchor_lag_calendar_days"],
                entry_adjusted_close=row["entry_adjusted_close"],
                horizon_sessions_available=int(row["horizon_sessions_available"]),
                fm252=row["fm252"],
                max_multiple_observed=row["max_multiple_observed"],
                outcome_class=row["outcome_class"],
                time_to_2x_sessions=row["time_to_2x_sessions"],
                time_to_3x_sessions=row["time_to_3x_sessions"],
                time_to_5x_sessions=row["time_to_5x_sessions"],
                time_to_7x_sessions=row["time_to_7x_sessions"],
                time_to_10x_sessions=row["time_to_10x_sessions"],
                outcome_status=row["outcome_status"],
            )
            error = prediction_error_class(
                precision_confirmed=bool(row["precision_confirmed"]),
                outcome=outcome,
            )
            if error:
                counts[error] += 1

        return FalsePositiveBreakdown(
            model_version=model_version,
            true_positive=counts["TP"],
            near_miss_false_positive=counts["NEAR_MISS_FP"],
            magnitude_false_positive=counts["MAGNITUDE_FP"],
            strong_winner_false_positive=counts["STRONG_WINNER_FP"],
            hard_false_positive=counts["HARD_FP"],
        )

    def route_performance(
        self,
        *,
        model_version: str,
    ) -> list[RoutePerformance]:
        rows = self.store.connection.execute(
            """
            SELECT a.route,a.score,b.return_12m
            FROM analysis_runs a
            JOIN backtest_results b ON b.analysis_id=a.analysis_id
            WHERE a.model_version=?
              AND a.route IS NOT NULL
              AND a.status='READY'
              AND b.outcome_status='READY'
            """,
            (model_version,),
        ).fetchall()

        grouped: dict[str, list] = defaultdict(list)
        for row in rows:
            grouped[str(row["route"])].append(row)

        output: list[RoutePerformance] = []
        for route in sorted(grouped):
            group = grouped[route]
            scores = [float(r["score"]) for r in group if r["score"] is not None]
            returns = [
                float(r["return_12m"]) for r in group if r["return_12m"] is not None
            ]
            output.append(
                RoutePerformance(
                    route=route,
                    count=len(group),
                    average_score=fmean(scores) if scores else None,
                    average_return_12m=fmean(returns) if returns else None,
                )
            )
        return output

    def compare_models(
        self,
        *,
        model_a: str,
        model_b: str,
    ) -> ModelComparison:
        rows = self.store.connection.execute(
            """
            SELECT
                a.score AS score_a,
                b.score AS score_b,
                a.precision_confirmed AS precision_a,
                b.precision_confirmed AS precision_b,
                o.fm252 AS fm252
            FROM backtest_predictions a
            JOIN backtest_predictions b
              ON b.observation_id=a.observation_id
            JOIN forward_outcomes o
              ON o.observation_id=a.observation_id
            WHERE a.model_version=?
              AND b.model_version=?
              AND a.status='READY'
              AND b.status='READY'
              AND o.outcome_status='READY'
            """,
            (model_a, model_b),
        ).fetchall()

        scores_a = [float(r["score_a"]) for r in rows if r["score_a"] is not None]
        scores_b = [float(r["score_b"]) for r in rows if r["score_b"] is not None]
        paired_scores = [
            (float(r["score_a"]), float(r["score_b"]))
            for r in rows
            if r["score_a"] is not None and r["score_b"] is not None
        ]
        differences = [b - a for a, b in paired_scores]

        precision_a = [bool(r["precision_a"]) for r in rows]
        precision_b = [bool(r["precision_b"]) for r in rows]
        return ModelComparison(
            model_a=model_a,
            model_b=model_b,
            paired_observations=len(rows),
            average_score_a=fmean(scores_a) if scores_a else None,
            average_score_b=fmean(scores_b) if scores_b else None,
            average_score_difference_b_minus_a=(
                fmean(differences) if differences else None
            ),
            precision_confirmed_a=sum(precision_a),
            precision_confirmed_b=sum(precision_b),
            precision_agreement=sum(
                1 for a, b in zip(precision_a, precision_b) if a == b
            ),
            precision_disagreement=sum(
                1 for a, b in zip(precision_a, precision_b) if a != b
            ),
            true_10x_observations=sum(
                1 for row in rows
                if row["fm252"] is not None and float(row["fm252"]) >= 10.0
            ),
        )
