from datetime import date

import pytest

from scripts.sync_free_pit_universe import month_end_dates


def test_month_end_dates_are_deterministic_and_bounded() -> None:
    assert month_end_dates(date(2024, 1, 1), date(2024, 3, 31)) == [
        date(2024, 1, 31),
        date(2024, 2, 29),
        date(2024, 3, 31),
    ]


def test_month_end_dates_reject_reverse_window() -> None:
    with pytest.raises(ValueError):
        month_end_dates(date(2024, 3, 1), date(2024, 1, 1))
