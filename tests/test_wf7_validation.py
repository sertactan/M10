from core.backtest.wf7_validation import (
    VALIDATION_POLICY_VERSION,
    average_precision_10x,
    calibration_bucket,
    threshold_metrics,
)


ROWS=[
    {"security_id":"A","as_of_date":"2020-01-01","v141_score":90.0,"fm252":10.5,"time_to_10x_sessions":100},
    {"security_id":"B","as_of_date":"2020-01-01","v141_score":85.0,"fm252":8.0,"time_to_10x_sessions":None},
    {"security_id":"C","as_of_date":"2020-01-01","v141_score":80.0,"fm252":5.5,"time_to_10x_sessions":None},
    {"security_id":"D","as_of_date":"2020-01-01","v141_score":70.0,"fm252":2.5,"time_to_10x_sessions":None},
    {"security_id":"E","as_of_date":"2020-01-01","v141_score":60.0,"fm252":1.0,"time_to_10x_sessions":None},
]


def test_wf7_threshold_metrics_and_lift() -> None:
    m=threshold_metrics(
        ROWS,selector="SCORE_GE_80",threshold=80,
        base_rate_10x_pct=20.0,total_true10=1,
    )
    assert m.selected_n==3
    assert m.true10_n==1
    assert round(m.precision_10x_pct,6)==round(100/3,6)
    assert m.recall_10x_pct==100.0
    assert round(m.lift_vs_base,6)==round((100/3)/20,6)
    assert round(m.near_miss_rate_pct,6)==round(100/3,6)
    assert round(m.magnitude_fp_rate_pct,6)==round(100/3,6)


def test_wf7_average_precision_is_rank_sensitive() -> None:
    assert average_precision_10x(ROWS)==1.0
    worse=list(ROWS)
    worse[0]=dict(worse[0],v141_score=50.0)
    assert average_precision_10x(worse) < 1.0


def test_wf7_calibration_fails_closed_below_30() -> None:
    b=calibration_bucket(ROWS,80,101,"80+")
    assert b["sample_size"]==3
    assert b["status"]=="INCONCLUSIVE_N_LT_30"
    assert b["p10_plus_pct"] is None


def test_wf7_policy_version() -> None:
    assert VALIDATION_POLICY_VERSION=="WF7_VALIDATION_POLICY_V1_2026-10-07"
