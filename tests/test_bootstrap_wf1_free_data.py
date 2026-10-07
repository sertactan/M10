from argparse import Namespace
from datetime import date

import pytest

from scripts.bootstrap_wf1_free_data import main
from scripts.sync_free_pit_universe import month_end_dates


def test_default_wf1_window_has_expected_month_end_count() -> None:
    dates = month_end_dates(date(2013, 1, 1), date(2024, 12, 31))
    assert len(dates) == 144
    assert dates[0] == date(2013, 1, 31)
    assert dates[-1] == date(2024, 12, 31)
