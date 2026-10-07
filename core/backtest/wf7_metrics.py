from __future__ import annotations

from dataclasses import dataclass
from statistics import median


POLICY_VERSION = "WF7_VALIDATION_POLICY_V1_2026-10-07"
CANONICAL_THRESHOLDS = (75.0, 80.0)
SCORE_BANDS = (
    (50.0,60.0,"50-59"),
    (60.0,70.0,"60-69"),
    (70.0,80.0,"70-79"),
    (80.0,90.0,"80-89"),
    (90.0,101.0,"90+"),
)


@dataclass(frozen=True)
class ValidationRow:
    score: float | None
    fm252: float | None
    outcome_status: str
    time_to_10x_sessions: int | None = None
    max_multiple_observed: float | None = None
    route: str | None = None


@dataclass(frozen=True)
class ThresholdMetrics:
    threshold: float
    sample_n: int
    predicted_positive_n: int
    true_10x_n: int
    true_positive_n: int
    precision: float | None
    recall: float | None
    lift: float | None
    near_miss_rate: float | None
    magnitude_fp_rate: float | None
    winner_fp_rate: float | None
    hard_fp_rate: float | None
    median_lead_time_sessions: float | None
    median_forward_max_multiple: float | None


def ready_rows(rows):
    return [
        row for row in rows
        if row.outcome_status=="READY"
        and row.score is not None
        and row.fm252 is not None
    ]


def _ratio(n: int, d: int) -> float | None:
    return (float(n)/float(d)) if d else None


def threshold_metrics(rows, threshold: float) -> ThresholdMetrics:
    sample=ready_rows(rows)
    positives=[row for row in sample if float(row.score) >= float(threshold)]
    actual=[row for row in sample if float(row.fm252) >= 10.0]
    tp=[row for row in positives if float(row.fm252) >= 10.0]
    near=[row for row in positives if 7.0 <= float(row.fm252) < 10.0]
    magnitude=[row for row in positives if 5.0 <= float(row.fm252) < 7.0]
    winner=[row for row in positives if 3.0 <= float(row.fm252) < 5.0]
    hard=[row for row in positives if float(row.fm252) < 3.0]

    precision=_ratio(len(tp),len(positives))
    recall=_ratio(len(tp),len(actual))
    prevalence=_ratio(len(actual),len(sample))
    lift=(precision/prevalence) if precision is not None and prevalence not in (None,0) else None

    lead=[float(row.time_to_10x_sessions) for row in tp if row.time_to_10x_sessions is not None]
    maxes=[
        float(row.max_multiple_observed)
        for row in positives
        if row.max_multiple_observed is not None
    ]
    return ThresholdMetrics(
        threshold=float(threshold),
        sample_n=len(sample),
        predicted_positive_n=len(positives),
        true_10x_n=len(actual),
        true_positive_n=len(tp),
        precision=precision,
        recall=recall,
        lift=lift,
        near_miss_rate=_ratio(len(near),len(positives)),
        magnitude_fp_rate=_ratio(len(magnitude),len(positives)),
        winner_fp_rate=_ratio(len(winner),len(positives)),
        hard_fp_rate=_ratio(len(hard),len(positives)),
        median_lead_time_sessions=(median(lead) if lead else None),
        median_forward_max_multiple=(median(maxes) if maxes else None),
    )


def top_n_metrics(rows, n: int) -> ThresholdMetrics:
    if n <= 0:
        raise ValueError("n must be positive")
    sample=ready_rows(rows)
    ranked=sorted(sample,key=lambda row: float(row.score),reverse=True)
    if not ranked:
        return threshold_metrics([],101.0)
    selected=ranked[:n]
    cutoff=float(selected[-1].score)
    # Exact top-N semantics: evaluate selected rows only, while recall/prevalence
    # denominators remain the full READY sample.
    actual=[row for row in sample if float(row.fm252) >= 10.0]
    tp=[row for row in selected if float(row.fm252) >= 10.0]
    near=[row for row in selected if 7.0 <= float(row.fm252) < 10.0]
    magnitude=[row for row in selected if 5.0 <= float(row.fm252) < 7.0]
    winner=[row for row in selected if 3.0 <= float(row.fm252) < 5.0]
    hard=[row for row in selected if float(row.fm252) < 3.0]
    precision=_ratio(len(tp),len(selected))
    prevalence=_ratio(len(actual),len(sample))
    lead=[float(r.time_to_10x_sessions) for r in tp if r.time_to_10x_sessions is not None]
    maxes=[float(r.max_multiple_observed) for r in selected if r.max_multiple_observed is not None]
    return ThresholdMetrics(
        threshold=cutoff,sample_n=len(sample),predicted_positive_n=len(selected),
        true_10x_n=len(actual),true_positive_n=len(tp),precision=precision,
        recall=_ratio(len(tp),len(actual)),
        lift=(precision/prevalence) if precision is not None and prevalence not in (None,0) else None,
        near_miss_rate=_ratio(len(near),len(selected)),
        magnitude_fp_rate=_ratio(len(magnitude),len(selected)),
        winner_fp_rate=_ratio(len(winner),len(selected)),
        hard_fp_rate=_ratio(len(hard),len(selected)),
        median_lead_time_sessions=(median(lead) if lead else None),
        median_forward_max_multiple=(median(maxes) if maxes else None),
    )


def pr_auc_average_precision(rows) -> float | None:
    """Deterministic PR-AUC policy: non-interpolated Average Precision."""
    sample=ready_rows(rows)
    ranked=sorted(sample,key=lambda row: float(row.score),reverse=True)
    positives=sum(float(row.fm252) >= 10.0 for row in ranked)
    if not ranked or positives == 0:
        return None
    tp=0
    accum=0.0
    for rank,row in enumerate(ranked,start=1):
        if float(row.fm252) >= 10.0:
            tp+=1
            accum += tp / rank
    return accum / positives


def calibration_bins(rows) -> list[dict]:
    sample=ready_rows(rows)
    out=[]
    for low,high,label in SCORE_BANDS:
        cohort=[r for r in sample if low <= float(r.score) < high]
        n=len(cohort)
        if not n:
            out.append({"band":label,"n":0,"p2":None,"p5":None,"p10":None})
            continue
        out.append({
            "band":label,
            "n":n,
            "p2":sum(float(r.fm252)>=2.0 for r in cohort)/n,
            "p5":sum(float(r.fm252)>=5.0 for r in cohort)/n,
            "p10":sum(float(r.fm252)>=10.0 for r in cohort)/n,
        })
    return out
