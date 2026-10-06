from __future__ import annotations

import argparse
import calendar
import csv
from datetime import date, timedelta
from pathlib import Path

from core.historical.s16_event_anchor import resolve_event_anchor
from core.historical.s16_runtime import (
    load_source_bars,
    resolve_security_id,
    select_adjusted_series,
)
from data.database.sqlite_store import SQLiteStore
from data.storage.parquet_price_store import ParquetPriceStore


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--parquet-root", required=True, type=Path)
    parser.add_argument(
        "--positives",
        type=Path,
        default=Path("data/seeds/s16_positive_events.csv"),
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    store = SQLiteStore(args.db)
    parquet = ParquetPriceStore(args.parquet_root)
    with args.positives.open(newline="", encoding="utf-8") as handle:
        seeds = list(csv.DictReader(handle))

    output: list[dict[str, object]] = []
    for seed in seeds:
        year, month = (int(x) for x in seed["event_period"].split("-", 1))
        month_start = date(year, month, 1)
        month_end = date(year, month, calendar.monthrange(year, month)[1])
        security_id = resolve_security_id(
            store.connection,
            ticker=seed["ticker"],
            as_of_date=month_end,
        )
        if security_id is None:
            output.append({
                **seed,
                "security_id": "",
                "as_of_date": "",
                "event_date": "",
                "resolution": "UNRESOLVED_SECURITY_ID",
                "strict_5d_10x_from_prior_close": "",
                "observed_multiple": "",
            })
            continue

        start = month_start - timedelta(days=15)
        end = month_end + timedelta(days=15)
        series = select_adjusted_series(
            store.connection,
            security_id=security_id,
            start_date=start,
            end_date=end,
        )
        if series is None:
            output.append({
                **seed,
                "security_id": security_id,
                "as_of_date": "",
                "event_date": "",
                "resolution": "UNRESOLVED_ADJUSTED_PRICE_SERIES",
                "strict_5d_10x_from_prior_close": "",
                "observed_multiple": "",
            })
            continue

        bars = load_source_bars(
            parquet, series=series, start_date=start, end_date=end
        )
        anchor = resolve_event_anchor(
            ticker=seed["ticker"],
            event_period=seed["event_period"],
            measurement_type=seed["measurement_type"],
            bars=bars,
        )
        output.append({
            **seed,
            "security_id": security_id,
            "as_of_date": anchor.as_of_date.isoformat() if anchor.as_of_date else "",
            "event_date": anchor.event_date.isoformat() if anchor.event_date else "",
            "resolution": anchor.resolution,
            "strict_5d_10x_from_prior_close": (
                "" if anchor.strict_5d_10x_from_prior_close is None
                else str(anchor.strict_5d_10x_from_prior_close).lower()
            ),
            "observed_multiple": (
                "" if anchor.observed_multiple is None
                else f"{anchor.observed_multiple:.8f}"
            ),
        })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output[0]))
        writer.writeheader()
        writer.writerows(output)
    print(f"wrote {len(output)} event-anchor rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
