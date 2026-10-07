from datetime import date

import pytest

from core.backtest.wf6_walk_forward import expanding_folds
from core.backtest.wf6_policy import (
    EXCLUDE_TARGET_SECURITY_FROM_HISTORICAL_CONTROLS,
    LEAKAGE_POLICY_VERSION,
    MODEL_TUNING_ALLOWED,
)


def test_wf6_expanding_folds_2018_2023() -> None:
    folds=expanding_folds(
        reference_start_year=2013,
        first_test_year=2018,
        last_test_year=2023,
    )
    assert len(folds)==6
    assert folds[0].reference_start==date(2013,1,1)
    assert folds[0].reference_end==date(2017,12,31)
    assert folds[0].test_start==date(2018,1,1)
    assert folds[-1].reference_end==date(2022,12,31)
    assert folds[-1].test_end==date(2023,12,31)


def test_wf6_is_validation_not_model_tuning() -> None:
    assert LEAKAGE_POLICY_VERSION=="WF6_LEAKAGE_POLICY_V1_2026-10-07"
    assert MODEL_TUNING_ALLOWED is False
    assert EXCLUDE_TARGET_SECURITY_FROM_HISTORICAL_CONTROLS is True


def test_wf6_rejects_invalid_fold_window() -> None:
    with pytest.raises(ValueError):
        expanding_folds(reference_start_year=2018,first_test_year=2018,last_test_year=2023)
