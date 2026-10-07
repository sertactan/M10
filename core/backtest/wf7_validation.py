from __future__ import annotations

import math
import statistics
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone


VALIDATION_POLICY_VERSION = "WF7_VALIDATION_POLICY_V1_2026-10-07"

SCORE_BUCKETS = (
    (0.0,55.0,"<55"),
    (55.0,65.0,"55-64"),
    (65.0,75.0,"65-74"),
    (75.0,80.0,"75-79"),
    (80.0,85.0,"80-84"),
    (85.0,101.0,"85+"),
)


@dataclass(frozen=True)
class ThresholdMetrics:
    selector: str
    threshold: float | None
    selected_n: int
    true10_n: int
    precision_10x_pct: float | None
    recall_10x_pct: float | None
    lift_vs_base: float | None
    near_miss_rate_pct: float | None
    magnitude_fp_rate_pct: float | None
    strong_winner_fp_rate_pct: float | None
    hard_fp_rate_pct: float | None
    median_fm252: float | None
    median_time_to_10x_sessions: float | None


def _pct(num: int, den: int) -> float | None:
    return None if den <= 0 else 100.0 * num / den


def _median(values) -> float | None:
    xs=[float(v) for v in values if v is not None]
    return statistics.median(xs) if xs else None


def threshold_metrics(
    rows: list[dict],
    *,
    selector: str,
    base_rate_10x_pct: float | None,
    total_true10: int,
    threshold: float | None=None,
    top_n: int | None=None,
) -> ThresholdMetrics:
    scored=[r for r in rows if r.get("v141_score") is not None]
    if top_n is not None:
        selected=sorted(
            scored,
            key=lambda r: (-float(r["v141_score"]),str(r.get("as_of_date","")),str(r.get("security_id",""))),
        )[:top_n]
    elif threshold is not None:
        selected=[r for r in scored if float(r["v141_score"]) >= threshold]
    else:
        raise ValueError("threshold or top_n is required")

    n=len(selected)
    true10=sum(float(r["fm252"]) >= 10.0 for r in selected)
    precision=_pct(true10,n)
    recall=_pct(true10,total_true10)
    lift=(
        precision / base_rate_10x_pct
        if precision is not None and base_rate_10x_pct not in (None,0.0)
        else None
    )
    return ThresholdMetrics(
        selector=selector,
        threshold=threshold,
        selected_n=n,
        true10_n=true10,
        precision_10x_pct=precision,
        recall_10x_pct=recall,
        lift_vs_base=lift,
        near_miss_rate_pct=_pct(sum(7.0 <= float(r["fm252"]) < 10.0 for r in selected),n),
        magnitude_fp_rate_pct=_pct(sum(5.0 <= float(r["fm252"]) < 7.0 for r in selected),n),
        strong_winner_fp_rate_pct=_pct(sum(3.0 <= float(r["fm252"]) < 5.0 for r in selected),n),
        hard_fp_rate_pct=_pct(sum(float(r["fm252"]) < 3.0 for r in selected),n),
        median_fm252=_median(r["fm252"] for r in selected),
        median_time_to_10x_sessions=_median(r.get("time_to_10x_sessions") for r in selected),
    )


def average_precision_10x(rows: list[dict]) -> float | None:
    """Standard average precision on scored READY OOS observations."""
    scored=sorted(
        [r for r in rows if r.get("v141_score") is not None],
        key=lambda r: -float(r["v141_score"]),
    )
    positives=sum(float(r["fm252"]) >= 10.0 for r in scored)
    if positives == 0:
        return None
    hit=0
    precision_sum=0.0
    for rank,row in enumerate(scored,start=1):
        if float(row["fm252"]) >= 10.0:
            hit+=1
            precision_sum += hit / rank
    return precision_sum / positives


def calibration_bucket(rows: list[dict], low: float, high: float, label: str) -> dict:
    cohort=[
        r for r in rows
        if r.get("v141_score") is not None
        and low <= float(r["v141_score"]) < high
    ]
    n=len(cohort)
    if n < 30:
        quality="INSUFFICIENT"
        status="INCONCLUSIVE_N_LT_30"
    elif n < 50:
        quality="REDUCED_SAMPLE"
        status="READY"
    else:
        quality="NORMAL"
        status="READY"

    def observed_rate(mult: float) -> float | None:
        if status != "READY":
            return None
        return _pct(sum(float(r["fm252"]) >= mult for r in cohort),n)

    return {
        "bucket_label":label,
        "score_low":low,
        "score_high":high,
        "sample_size":n,
        "true10_count":sum(float(r["fm252"]) >= 10.0 for r in cohort),
        "p2_plus_pct":observed_rate(2.0),
        "p5_plus_pct":observed_rate(5.0),
        "p7_plus_pct":observed_rate(7.0),
        "p10_plus_pct":observed_rate(10.0),
        "median_fm252":_median(r["fm252"] for r in cohort),
        "sample_quality":quality,
        "status":status,
    }


class WF7ValidationCalibrationEngine:
    """Validate/calibrate only from WF6 OOS READY market-prevalence observations."""

    def __init__(self, store) -> None:
        self.store=store

    def _ready_rows(self, wf6_run_id: str) -> list[dict]:
        rows=self.store.connection.execute(
            """
            SELECT o.*
            FROM wf6_oos_observations o
            JOIN wf6_walk_forward_folds f ON f.fold_id=o.fold_id
            WHERE f.run_id=?
              AND o.outcome_status='READY'
              AND o.fm252 IS NOT NULL
            ORDER BY o.as_of_date,o.security_id,o.source_observation_id
            """,
            (wf6_run_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def create_run(self, wf6_run_id: str) -> str:
        source=self.store.connection.execute(
            "SELECT * FROM wf6_walk_forward_runs WHERE run_id=?",
            (wf6_run_id,),
        ).fetchone()
        if source is None:
            raise ValueError("unknown WF6 walk-forward run")
        if str(source["status"]) not in {"COMPLETE","COMPLETE_WITH_BLOCKERS"}:
            raise ValueError("WF6 run must be completed before WF7 validation")
        run_id=str(uuid.uuid4())
        self.store.connection.execute(
            """
            INSERT INTO wf7_validation_runs (
                run_id,wf6_run_id,model_version,validation_policy,status,created_at
            ) VALUES (?,?,?,?,?,?)
            """,
            (
                run_id,wf6_run_id,"S15.3_V1.4.1",
                VALIDATION_POLICY_VERSION,"ACTIVE",
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self.store.connection.commit()
        return run_id

    def run(self, *, wf6_run_id: str, run_id: str | None=None) -> str:
        run_id=run_id or self.create_run(wf6_run_id)
        rows=self._ready_rows(wf6_run_id)
        ready_n=len(rows)
        scored=[r for r in rows if r.get("v141_score") is not None]
        scored_n=len(scored)
        true10=sum(float(r["fm252"]) >= 10.0 for r in rows)
        base_rate=_pct(true10,ready_n)
        pr_ap=average_precision_10x(rows)

        metrics=[
            threshold_metrics(
                rows,selector=f"SCORE_GE_{int(t)}",threshold=t,
                base_rate_10x_pct=base_rate,total_true10=true10,
            )
            for t in (65.0,75.0,80.0,85.0)
        ]
        metrics.extend([
            threshold_metrics(
                rows,selector="TOP20",top_n=20,
                base_rate_10x_pct=base_rate,total_true10=true10,
            ),
            threshold_metrics(
                rows,selector="TOP50",top_n=50,
                base_rate_10x_pct=base_rate,total_true10=true10,
            ),
        ])

        now=datetime.now(timezone.utc).isoformat()
        for m in metrics:
            self.store.connection.execute(
                """
                INSERT INTO wf7_threshold_metrics (
                    run_id,selector,threshold,selected_n,true10_n,
                    precision_10x_pct,recall_10x_pct,lift_vs_base,
                    near_miss_rate_pct,magnitude_fp_rate_pct,
                    strong_winner_fp_rate_pct,hard_fp_rate_pct,
                    median_fm252,median_time_to_10x_sessions,created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(run_id,selector) DO UPDATE SET
                    threshold=excluded.threshold,selected_n=excluded.selected_n,
                    true10_n=excluded.true10_n,
                    precision_10x_pct=excluded.precision_10x_pct,
                    recall_10x_pct=excluded.recall_10x_pct,
                    lift_vs_base=excluded.lift_vs_base,
                    near_miss_rate_pct=excluded.near_miss_rate_pct,
                    magnitude_fp_rate_pct=excluded.magnitude_fp_rate_pct,
                    strong_winner_fp_rate_pct=excluded.strong_winner_fp_rate_pct,
                    hard_fp_rate_pct=excluded.hard_fp_rate_pct,
                    median_fm252=excluded.median_fm252,
                    median_time_to_10x_sessions=excluded.median_time_to_10x_sessions,
                    created_at=excluded.created_at
                """,
                (
                    run_id,m.selector,m.threshold,m.selected_n,m.true10_n,
                    m.precision_10x_pct,m.recall_10x_pct,m.lift_vs_base,
                    m.near_miss_rate_pct,m.magnitude_fp_rate_pct,
                    m.strong_winner_fp_rate_pct,m.hard_fp_rate_pct,
                    m.median_fm252,m.median_time_to_10x_sessions,now,
                ),
            )

        for low,high,label in SCORE_BUCKETS:
            b=calibration_bucket(rows,low,high,label)
            self.store.connection.execute(
                """
                INSERT INTO wf7_calibration_buckets (
                    run_id,bucket_label,score_low,score_high,sample_size,
                    true10_count,p2_plus_pct,p5_plus_pct,p7_plus_pct,p10_plus_pct,
                    median_fm252,sample_quality,status,created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(run_id,bucket_label) DO UPDATE SET
                    sample_size=excluded.sample_size,
                    true10_count=excluded.true10_count,
                    p2_plus_pct=excluded.p2_plus_pct,
                    p5_plus_pct=excluded.p5_plus_pct,
                    p7_plus_pct=excluded.p7_plus_pct,
                    p10_plus_pct=excluded.p10_plus_pct,
                    median_fm252=excluded.median_fm252,
                    sample_quality=excluded.sample_quality,
                    status=excluded.status,created_at=excluded.created_at
                """,
                (
                    run_id,b["bucket_label"],b["score_low"],b["score_high"],
                    b["sample_size"],b["true10_count"],b["p2_plus_pct"],
                    b["p5_plus_pct"],b["p7_plus_pct"],b["p10_plus_pct"],
                    b["median_fm252"],b["sample_quality"],b["status"],now,
                ),
            )

        routes=sorted({str(r["primary_route"]) for r in scored if r.get("primary_route")})
        for route in routes:
            cohort=[r for r in scored if str(r.get("primary_route"))==route]
            n=len(cohort)
            r_true=sum(float(r["fm252"])>=10.0 for r in cohort)
            self.store.connection.execute(
                """
                INSERT INTO wf7_route_metrics (
                    run_id,route,sample_size,true10_count,p10_plus_pct,
                    p5_plus_pct,median_fm252,created_at
                ) VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(run_id,route) DO UPDATE SET
                    sample_size=excluded.sample_size,
                    true10_count=excluded.true10_count,
                    p10_plus_pct=excluded.p10_plus_pct,
                    p5_plus_pct=excluded.p5_plus_pct,
                    median_fm252=excluded.median_fm252,
                    created_at=excluded.created_at
                """,
                (
                    run_id,route,n,r_true,_pct(r_true,n),
                    _pct(sum(float(r["fm252"])>=5.0 for r in cohort),n),
                    _median(r["fm252"] for r in cohort),now,
                ),
            )

        self.store.connection.execute(
            """
            INSERT INTO wf7_validation_summary (
                run_id,ready_oos_n,scored_ready_n,score_coverage_pct,
                true10_count,base_rate_10x_pct,pr_auc_average_precision,
                probability_head_status,created_at
            ) VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(run_id) DO UPDATE SET
                ready_oos_n=excluded.ready_oos_n,
                scored_ready_n=excluded.scored_ready_n,
                score_coverage_pct=excluded.score_coverage_pct,
                true10_count=excluded.true10_count,
                base_rate_10x_pct=excluded.base_rate_10x_pct,
                pr_auc_average_precision=excluded.pr_auc_average_precision,
                probability_head_status=excluded.probability_head_status,
                created_at=excluded.created_at
            """,
            (
                run_id,ready_n,scored_n,_pct(scored_n,ready_n),
                true10,base_rate,(100.0*pr_ap if pr_ap is not None else None),
                "NOT_AVAILABLE_SCORE_IS_NOT_PROBABILITY",now,
            ),
        )
        self.store.connection.execute(
            "UPDATE wf7_validation_runs SET status='COMPLETE',completed_at=? WHERE run_id=?",
            (now,run_id),
        )
        self.store.connection.commit()
        return run_id
