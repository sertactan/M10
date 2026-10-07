from datetime import date

from core.backtest.wf5_schedule import monthly_snapshot_dates


def test_wf5_monthly_schedule_2013_2024_is_144_snapshots() -> None:
    dates=monthly_snapshot_dates(date(2013,1,1),date(2024,12,31))
    assert len(dates)==144
    assert dates[0]==date(2013,1,31)
    assert dates[-1]==date(2024,12,31)


def test_wf5_schedule_rejects_reverse_range() -> None:
    try:
        monthly_snapshot_dates(date(2024,2,1),date(2024,1,1))
    except ValueError:
        pass
    else:
        raise AssertionError("reverse range must fail")
