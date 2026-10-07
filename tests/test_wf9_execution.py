from datetime import date

from core.backtest.wf5_schedule import monthly_snapshot_dates
from core.backtest.wf9_execution import WF9PreflightReport


def test_wf9_default_window_has_144_monthly_snapshots() -> None:
    dates=monthly_snapshot_dates(date(2013,1,1),date(2024,12,31))
    assert len(dates)==144


def test_wf9_preflight_ready_only_without_blockers() -> None:
    ok=WF9PreflightReport(
        start_date=date(2013,1,1),
        end_date=date(2024,12,31),
        requested_snapshot_dates=144,
        existing_snapshot_dates=144,
        exact_pit_dates=144,
        any_adjusted_price_dates=144,
        total_universe_observations=1000,
        total_price_covered=990,
        blockers=(),
        warnings=("PARTIAL_ADJUSTED_PRICE_COVERAGE:990/1000",),
    )
    assert ok.ready is True
    blocked=WF9PreflightReport(
        start_date=ok.start_date,end_date=ok.end_date,
        requested_snapshot_dates=144,existing_snapshot_dates=100,
        exact_pit_dates=100,any_adjusted_price_dates=0,
        total_universe_observations=1000,total_price_covered=0,
        blockers=("MISSING_PIT_SNAPSHOT_DATES:100/144",),
        warnings=(),
    )
    assert blocked.ready is False
