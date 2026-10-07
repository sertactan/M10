from core.backtest.wf7_metrics import (
    ValidationRow,
    calibration_bins,
    pr_auc_average_precision,
    threshold_metrics,
    top_n_metrics,
)
from core.backtest.wf7_policy import (
    ALLOW_HOLDOUT_THRESHOLD_TUNING,
    PRECISION_THRESHOLD,
    STRONG_WATCH_THRESHOLD,
)


def _rows():
    return [
        ValidationRow(90,12,"READY",100,12),
        ValidationRow(85,8,"READY",None,8),
        ValidationRow(82,6,"READY",None,6),
        ValidationRow(81,4,"READY",None,4),
        ValidationRow(80,2,"READY",None,2),
        ValidationRow(79,11,"READY",120,11),
        ValidationRow(78,1.5,"READY",None,1.5),
        ValidationRow(99,None,"CENSORED",None,None),
    ]


def test_canonical_threshold_metrics_preserve_false_positive_bands() -> None:
    m=threshold_metrics(_rows(),80)
    assert m.predicted_positive_n==5
    assert m.true_positive_n==1
    assert m.precision==0.2
    assert m.near_miss_rate==0.2
    assert m.magnitude_fp_rate==0.2
    assert m.winner_fp_rate==0.2
    assert m.hard_fp_rate==0.2


def test_top_n_and_pr_auc_ignore_censored_rows() -> None:
    top=top_n_metrics(_rows(),3)
    assert top.predicted_positive_n==3
    assert top.true_positive_n==1
    assert pr_auc_average_precision(_rows()) is not None


def test_calibration_bins_are_empirical_frequencies_not_probabilities_from_score() -> None:
    bins=calibration_bins(_rows())
    band80=next(x for x in bins if x["band"]=="80-89")
    assert band80["n"]==4
    assert band80["p10"]==0.0


def test_wf7_never_tunes_holdout_thresholds() -> None:
    assert STRONG_WATCH_THRESHOLD==75.0
    assert PRECISION_THRESHOLD==80.0
    assert ALLOW_HOLDOUT_THRESHOLD_TUNING is False
