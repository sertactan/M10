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
from data.providers.massive_universe import MassiveUniverseProvider
from data.repositories.security_repository import SecurityRepository


UNIVERSE_PROVIDER_MODES = ("AUTO", "ALPHAVANTAGE", "MASSIVE")


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


async def _load_snapshot(
    *,
    as_of: date,
    mode: str,
    alpha: AlphaVantagePitUniverseProvider,
    massive: MassiveUniverseProvider,
):
    normalized = mode.upper()
    if normalized not in UNIVERSE_PROVIDER_MODES:
        raise ValueError(f"unsupported universe provider mode: {mode}")

    errors: list[str] = []
    candidates: list[str] = []
    if normalized == "ALPHAVANTAGE":
        candidates = ["ALPHAVANTAGE"]
    elif normalized == "MASSIVE":
        candidates = ["MASSIVE"]
    else:
        if alpha.configured:
            candidates.append("ALPHAVANTAGE")
        if massive.configured:
            candidates.append("MASSIVE")

    if not candidates:
        raise RuntimeError(
            "No PIT-capable historical universe provider is configured. "
            "Set ALPHAVANTAGE_API_KEY or MASSIVE_API_KEY."
        )

    for name in candidates:
        try:
            if name == "ALPHAVANTAGE":
                records = await alpha.list_historical_us_securities(as_of)
                return records, "ALPHAVANTAGE_PIT"
            records = await massive.list_us_securities(as_of=as_of, active=True)
            if not records:
                raise RuntimeError("Massive returned an empty PIT snapshot")
            return records, "MASSIVE_PIT"
        except AlphaVantagePitUnavailable as exc:
            errors.append(f"ALPHAVANTAGE: {exc}")
        except Exception as exc:
            errors.append(f"{name}: {exc}")

    raise RuntimeError(
        f"No PIT provider could load {as_of.isoformat()}: " + " | ".join(errors)
    )


async def run(
    start: date,
    end: date,
    *,
    overwrite: bool = False,
    provider_mode: str = "AUTO",
) -> int:
    root = Path(__file__).resolve().parents[1]
    app = AppContainer(root)
    app.initialize()
    try:
        alpha = AlphaVantagePitUniverseProvider()
        massive = MassiveUniverseProvider()
        repository = SecurityRepository(app.sqlite)
        completed = 0
        skipped = 0
        source_counts: dict[str, int] = {}

        for as_of in month_end_dates(start, end):
            existing = repository.universe_as_of(as_of)
            if existing and not overwrite:
                print(f"SKIP {as_of}: existing snapshot rows={len(existing)}")
                skipped += 1
                continue
            try:
                records, source = await _load_snapshot(
                    as_of=as_of,
                    mode=provider_mode,
                    alpha=alpha,
                    massive=massive,
                )
            except Exception as exc:
                # Completed snapshots remain durable. A rerun resumes from the
                # first missing month and may use another configured PIT source.
                print(f"STOP {as_of}: {exc}")
                print(
                    f"COMPLETED={completed} SKIPPED={skipped} "
                    f"SOURCES={source_counts}"
                )
                return 2

            count = repository.bulk_upsert_historical_snapshot(
                records,
                snapshot_date=as_of,
            )
            source_counts[source] = source_counts.get(source, 0) + 1
            print(f"OK {as_of}: rows={count} source={source}")
            completed += 1

        print(
            f"COMPLETE snapshots={completed} skipped={skipped} "
            f"sources={source_counts}"
        )
        return 0
    finally:
        app.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build month-end historical US PIT universe snapshots"
    )
    parser.add_argument("--start", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--provider",
        default="AUTO",
        choices=UNIVERSE_PROVIDER_MODES,
        help="AUTO prefers Alpha Vantage and falls back to Massive when configured.",
    )
    args = parser.parse_args()
    return asyncio.run(
        run(
            date.fromisoformat(args.start),
            date.fromisoformat(args.end),
            overwrite=args.overwrite,
            provider_mode=args.provider,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
