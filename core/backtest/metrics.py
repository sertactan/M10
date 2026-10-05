from __future__ import annotations

from core.backtest.contracts import ForwardOutcome


def prediction_error_class(
    *,
    precision_confirmed: bool,
    outcome: ForwardOutcome,
) -> str | None:
    """Canonical error class for a positive S15.3 prediction.

    CENSORED/PARTIAL/non-READY outcomes are excluded from binary primary metrics.
    """
    if not precision_confirmed or outcome.outcome_status != "READY" or outcome.fm252 is None:
        return None

    fm = outcome.fm252
    if fm >= 10:
        return "TP"
    if fm >= 7:
        return "NEAR_MISS_FP"
    if fm >= 5:
        return "MAGNITUDE_FP"
    if fm >= 3:
        return "STRONG_WINNER_FP"
    return "HARD_FP"
