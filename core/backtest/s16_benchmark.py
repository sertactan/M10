from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class S16BenchmarkRow:
    observation_id: str
    cohort: str
    v02_armed: float
    v02_ignition: float
    v03_armed: float
    v03_ignition: float
    hit_3x_high: bool
    hit_5x_high: bool
    hit_10x_high: bool
    hit_3x_close: bool
    hit_5x_close: bool
    hit_10x_close: bool


@dataclass(frozen=True)
class S16BinaryMetrics:
    score_field: str
    label_field: str
    threshold: float
    observations: int
    positives: int
    controls: int
    tp: int
    fp: int
    tn: int
    fn: int
    recall: float | None
    false_positive_rate: float | None
    specificity: float | None
    case_control_precision: float | None
    balanced_accuracy: float | None
    alert_rate: float

    @property
    def real_world_precision_available(self) -> bool:
        return False


def _ratio(num: int, den: int) -> float | None:
    return None if den <= 0 else num / den


def evaluate_threshold(
    rows: Iterable[S16BenchmarkRow],
    *,
    score_field: str,
    label_field: str,
    threshold: float,
) -> S16BinaryMetrics:
    items = list(rows)
    valid_scores = {"v02_armed", "v02_ignition", "v03_armed", "v03_ignition"}
    valid_labels = {
        "hit_3x_high", "hit_5x_high", "hit_10x_high",
        "hit_3x_close", "hit_5x_close", "hit_10x_close",
    }
    if score_field not in valid_scores:
        raise ValueError(f"unsupported score field: {score_field}")
    if label_field not in valid_labels:
        raise ValueError(f"unsupported label field: {label_field}")

    tp = fp = tn = fn = 0
    positives = controls = 0
    alerts = 0
    for row in items:
        label = bool(getattr(row, label_field))
        alert = float(getattr(row, score_field)) >= threshold
        if row.cohort == "POSITIVE":
            positives += 1
        elif row.cohort == "CONTROL":
            controls += 1
        else:
            raise ValueError(f"unsupported cohort: {row.cohort}")

        alerts += int(alert)
        if label and alert:
            tp += 1
        elif label and not alert:
            fn += 1
        elif not label and alert:
            fp += 1
        else:
            tn += 1

    recall = _ratio(tp, tp + fn)
    fpr = _ratio(fp, fp + tn)
    specificity = _ratio(tn, tn + fp)
    precision = _ratio(tp, tp + fp)
    balanced = (
        None if recall is None or specificity is None
        else (recall + specificity) / 2.0
    )
    return S16BinaryMetrics(
        score_field=score_field,
        label_field=label_field,
        threshold=float(threshold),
        observations=len(items),
        positives=positives,
        controls=controls,
        tp=tp, fp=fp, tn=tn, fn=fn,
        recall=recall,
        false_positive_rate=fpr,
        specificity=specificity,
        case_control_precision=precision,
        balanced_accuracy=balanced,
        alert_rate=(alerts / len(items) if items else 0.0),
    )


def benchmark_grid(
    rows: Iterable[S16BenchmarkRow],
    *,
    thresholds: Iterable[float] = (50, 55, 60, 65, 70, 75, 80, 85, 90),
) -> list[S16BinaryMetrics]:
    items = list(rows)
    scores = ("v02_armed", "v02_ignition", "v03_armed", "v03_ignition")
    labels = (
        "hit_3x_high", "hit_5x_high", "hit_10x_high",
        "hit_3x_close", "hit_5x_close", "hit_10x_close",
    )
    return [
        evaluate_threshold(
            items,
            score_field=score,
            label_field=label,
            threshold=float(threshold),
        )
        for score in scores
        for label in labels
        for threshold in thresholds
    ]
