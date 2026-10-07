from __future__ import annotations

import argparse
import asyncio
import calendar
from datetime import date
from pathlib import Path

from app.bootstrap import AppContainer
from data.providers.alpha_vantage_pit_universe import (
    AlphaVantagePitUnavailable,
    AlphaVantagePitUniverseProvider,
)
from data.repositories.security_repository import SecurityRepository


def month_end_dates(start: date, end: date) -> list[date]:
    if end < start:
        raise ValueError("end must be >= start")
    out: list[date] = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        last = calendar.monthrange(year, month)[1]
        candidate = date(year, month, last)
        if start <= candidate <= end:
            out.append(candidate)
        if month == 12:
            year, month = year + 1, 1
        else:
            month += 1
    return out


async def run(start: date, end: date, *, overwrite: bool = False) -> int:
    root = Path(__file__).resolve().parents[1]
    app = AppContainer(root)
    app.initialize()
    try:
        provider = AlphaVantagePitUniverseProvider()
        if not provider.configured:
            raise RuntimeError(
                "ALPHAVANTAGE_API_KEY is not configured. A free key is sufficient "
                "for the LISTING_STATUS workflow."
            )
        repository = SecurityRepository(app.sqlite)
        completed = 0
        skipped = 0
        for as_of in month_end_dates(start, end):
            existing = repository.universe_as_of(as_of)
            if existing and not overwrite:
                print(f"SKIP {as_of}: existing snapshot rows={len(existing)}")
                skipped += 1
                continue
            try:
                records = await provider.list_historical_us_securities(as_of)
            except AlphaVantagePitUnavailable as exc:
                # Free-plan rate limits/API notes are surfaced as unavailable.
                # Stop without deleting earlier completed snapshots; reruns are idempotent.
                print(f"STOP {as_of}: {exc}")
                print(f"COMPLETED={completed} SKIPPED={skipped}")
                return 2
            count = repository.bulk_upsert_historical_snapshot(
                records,
                snapshot_date=as_of,
            )
            print(f"OK {as_of}: rows={count}")
            completed += 1
        print(f"COMPLETE snapshots={completed} skipped={skipped}")
        return 0
    finally:
        app.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build free month-end historical US PIT universe snapshots"
    )
    parser.add_argument("--start", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    return asyncio.run(
        run(
            date.fromisoformat(args.start),
            date.fromisoformat(args.end),
            overwrite=args.overwrite,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
