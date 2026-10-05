from __future__ import annotations

from datetime import datetime, timezone

import pytest

from core.analytics.contracts import ScoreBucket
from core.analytics.model_analytics import AnalyticsInputError, ModelAnalytics
from data.database.sqlite_store import SQLiteStore


def _seed(store: SQLiteStore) -> None:
    now = datetime(2026, 10, 6, tzinfo=timezone.utc).isoformat()
    store.connection.execute(
        """
        INSERT INTO security_master (
            security_id,ticker,name,exchange,market,active,created_at,updated_at
        ) VALUES (?,?,?,?,?,?,?,?)
        """,
        ("SEC_A","AAA","AAA Inc.","NASDAQ","US",1,now,now),
    )
    outcomes = [
        ("SEC_A|2024-01-02","SEC_A","2024-01-02",12.0,"TRUE_10X"),
        ("SEC_A|2024-02-02","SEC_A","2024-02-02",8.0,"NEAR_MISS_10X"),
        ("SEC_A|2024-03-02","SEC_A","2024-03-02",5.5,"MAJOR_WINNER"),
        ("SEC_A|2024-04-02","SEC_A","2024-04-02",3.5,"STRONG_WINNER"),
        ("SEC_A|2024-05-02","SEC_A","2024-05-02",1.5,"FAILURE"),
    ]
    for observation_id, security_id, as_of, fm252, outcome_class in outcomes:
        store.connection.execute(
            """
            INSERT INTO forward_outcomes (
                observation_id,security_id,as_of_date_requested,anchor_session,
                anchor_lag_calendar_days,entry_adjusted_close,horizon_sessions_available,
                fm252,max_multiple_observed,outcome_class,time_to_2x_sessions,
                time_to_3x_sessions,time_to_5x_sessions,time_to_7x_sessions,
                time_to_10x_sessions,outcome_status,diagnostics_json,outcome_hash,created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                observation_id,security_id,as_of,as_of,0,10.0,252,
                fm252,fm252,outcome_class,None,None,None,None,None,
                "READY","{}","a"*64,now,
            ),
        )
    v12_scores = [82.0,78.0,74.0,69.0,65.0]
    v14_scores = [88.0,79.0,76.0,70.0,66.0]
    v12_precision = [1,1,1,1,1]
    v14_precision = [1,1,1,0,0]
    for i, observation in enumerate(outcomes):
        observation_id = observation[0]
        for version, score, precision in (
            ("S15.3_V1.2",v12_scores[i],v12_precision[i]),
            ("S15.3_V1.4",v14_scores[i],v14_precision[i]),
        ):
            store.connection.execute(
                """
                INSERT INTO backtest_predictions (
                    observation_id,model_version,score,precision_confirmed,status,score_hash,created_at
                ) VALUES (?,?,?,?,?,?,?)
                """,
                (observation_id,version,score,precision,"READY","b"*64,now),
            )

    for analysis_id, route, score, ret in (
        ("A1","F10",82.0,950.0),
        ("A2","F10",76.0,300.0),
        ("A3","Q10",72.0,120.0),
    ):
        store.connection.execute(
            """
            INSERT INTO analysis_runs (
                analysis_id,ticker,security_id,analysis_date,mode,model_version,
                data_snapshot_hash,model_config_hash,score,route,destination,prediction,
                status,created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                analysis_id,"AAA","SEC_A","2024-01-02","HISTORICAL","S15.3_V1.2",
                "c"*64,"d"*64,score,route,None,None,"READY",now,
            ),
        )
        store.connection.execute(
            """
            INSERT INTO backtest_results (
                analysis_id,entry_price,return_1m,return_3m,return_6m,return_12m,
                max_gain_12m,max_drawdown_12m,result_class,outcome_status
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (analysis_id,10.0,None,None,None,ret,None,None,"TEST","READY"),
        )
    store.connection.commit()


def test_score_bucket_stats_require_explicit_non_overlapping_buckets(tmp_path):
    store = SQLiteStore(tmp_path / "analytics.sqlite")
    store.initialize()
    try:
        _seed(store)
        analytics = ModelAnalytics(store)
        buckets = [
            ScoreBucket("65-75",65.0,75.0),
            ScoreBucket("75-85",75.0,85.0),
        ]
        rows = analytics.score_bucket_stats(
            model_version="S15.3_V1.2",
            buckets=buckets,
        )
        assert [row.count for row in rows] == [3,2]
        assert rows[0].true_10x == 0
        assert rows[1].true_10x == 1

        with pytest.raises(AnalyticsInputError, match="overlap"):
            analytics.score_bucket_stats(
                model_version="S15.3_V1.2",
                buckets=[
                    ScoreBucket("A",60.0,80.0),
                    ScoreBucket("B",70.0,90.0),
                ],
            )
    finally:
        store.close()


def test_false_positive_breakdown_reuses_phase6_classes(tmp_path):
    store = SQLiteStore(tmp_path / "analytics.sqlite")
    store.initialize()
    try:
        _seed(store)
        result = ModelAnalytics(store).false_positive_breakdown(
            model_version="S15.3_V1.2"
        )
        assert result.true_positive == 1
        assert result.near_miss_false_positive == 1
        assert result.magnitude_false_positive == 1
        assert result.strong_winner_false_positive == 1
        assert result.hard_false_positive == 1
    finally:
        store.close()


def test_route_performance_uses_persisted_historical_results(tmp_path):
    store = SQLiteStore(tmp_path / "analytics.sqlite")
    store.initialize()
    try:
        _seed(store)
        rows = ModelAnalytics(store).route_performance(
            model_version="S15.3_V1.2"
        )
        assert [row.route for row in rows] == ["F10","Q10"]
        assert rows[0].count == 2
        assert rows[0].average_score == pytest.approx(79.0)
        assert rows[0].average_return_12m == pytest.approx(625.0)
    finally:
        store.close()


def test_v12_v14_comparison_uses_paired_ready_observations(tmp_path):
    store = SQLiteStore(tmp_path / "analytics.sqlite")
    store.initialize()
    try:
        _seed(store)
        result = ModelAnalytics(store).compare_models(
            model_a="S15.3_V1.2",
            model_b="S15.3_V1.4",
        )
        assert result.paired_observations == 5
        assert result.true_10x_observations == 1
        assert result.precision_confirmed_a == 5
        assert result.precision_confirmed_b == 3
        assert result.precision_agreement == 3
        assert result.precision_disagreement == 2
        assert result.average_score_difference_b_minus_a == pytest.approx(4.2)
    finally:
        store.close()
