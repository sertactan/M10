from __future__ import annotations

import argparse
import csv
import math
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from statistics import pstdev

from data.database.sqlite_store import SQLiteStore
from data.repositories.fundamental_repository import FundamentalRepository
from data.storage.parquet_price_store import ParquetPriceStore
from core.historical.s16_runtime import select_adjusted_series


SOURCE_RANK = {"SEC_EDGAR": 0, "MASSIVE": 1, "FINNHUB": 2, "SIMFIN": 3, "FMP": 4}


def _latest_shares(repo: FundamentalRepository, security_id: str, as_of: datetime) -> float | None:
    rows = repo.source_facts_as_of(security_id, as_of, metric_name="SHARES_OUTSTANDING")
    if not rows:
        return None
    rows.sort(
        key=lambda row: (
            SOURCE_RANK.get(str(row["source"]), 99),
            str(row["period_end"]),
            str(row["available_at"]),
        ),
        reverse=False,
    )
    best_source_rank = SOURCE_RANK.get(str(rows[0]["source"]), 99)
    same_source = [
        row for row in rows
        if SOURCE_RANK.get(str(row["source"]), 99) == best_source_rank
    ]
    latest = max(same_source, key=lambda row: (str(row["period_end"]), str(row["available_at"])))
    value = float(latest["value"])
    return value if value > 0 else None


def _metrics(frame):
    frame = frame.sort_values("trade_date").tail(21)
    if len(frame) < 21:
        return None
    closes = [float(x) for x in frame["adjusted_close"]]
    if any(x <= 0 for x in closes):
        return None
    price = closes[-1]
    adv20 = sum(float(x) for x in frame.tail(20)["volume"]) / 20.0
    returns = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
    return {
        "price": price,
        "adv20": adv20,
        "volatility20": pstdev(returns),
        "mom5": price / closes[-6] - 1.0,
        "mom20": price / closes[-21] - 1.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--parquet-root", required=True, type=Path)
    parser.add_argument("--anchors", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    with args.anchors.open(newline="", encoding="utf-8") as handle:
        anchors = [row for row in csv.DictReader(handle) if row.get("as_of_date")]
    event_dates = sorted({date.fromisoformat(row["as_of_date"]) for row in anchors})
    if not event_dates:
        raise RuntimeError("no resolved event anchor dates")

    store = SQLiteStore(args.db)
    parquet = ParquetPriceStore(args.parquet_root)
    fundamentals = FundamentalRepository(store)
    output: list[dict[str, object]] = []

    for as_of_date in event_dates:
        as_of = datetime.combine(as_of_date, time.max, tzinfo=timezone.utc)
        securities = store.connection.execute(
            """
            SELECT *
            FROM security_master
            WHERE market='US'
              AND exchange IN ('NASDAQ','NYSE','AMEX')
              AND COALESCE(security_type,'CS')='CS'
              AND (ipo_date IS NULL OR ipo_date<=?)
              AND (delisted_date IS NULL OR delisted_date>=?)
            ORDER BY ticker
            """,
            (as_of_date.isoformat(), as_of_date.isoformat()),
        ).fetchall()

        for security in securities:
            security_id = str(security["security_id"])
            start = as_of_date - timedelta(days=60)
            series = select_adjusted_series(
                store.connection,
                security_id=security_id,
                start_date=start,
                end_date=as_of_date,
            )
            if series is None:
                continue
            frame = parquet.read_bars(
                security_id=security_id,
                source=str(series["source"]),
                source_symbol=str(series["source_symbol"]),
                start_date=start,
                end_date=as_of_date,
            )
            metrics = _metrics(frame)
            if metrics is None:
                continue
            shares = _latest_shares(fundamentals, security_id, as_of)
            if shares is None:
                continue

            ipo_date = (
                date.fromisoformat(str(security["ipo_date"]))
                if security["ipo_date"]
                else date.fromisoformat(str(series["start_date"]))
            )
            listing_age = max(0, (as_of_date - ipo_date).days)
            ipo_route = listing_age <= 7
            sector = str(security["sector"] or security["industry"] or "")
            output.append({
                "security_id": security_id,
                "ticker": str(security["ticker"]),
                "as_of_date": as_of_date.isoformat(),
                "market_cap": metrics["price"] * shares,
                "float_shares": shares,
                "price": metrics["price"],
                "adv20": metrics["adv20"],
                "volatility20": metrics["volatility20"],
                "mom5": metrics["mom5"],
                "mom20": metrics["mom20"],
                "sector": sector,
                "listing_age_days": listing_age,
                "security_type": "CS",
                "ipo_route": str(ipo_route).lower(),
                "supply_kind": "PIT_SHARES_OUTSTANDING_PROXY",
                "source_quality": "PIT_PROXY",
                "price_source": str(series["source"]),
            })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not output:
        raise RuntimeError(
            "no PIT match candidates materialized; historical adjusted price and "
            "PIT shares-outstanding coverage are required"
        )
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output[0]))
        writer.writeheader()
        writer.writerows(output)
    print(f"wrote {len(output)} PIT candidate snapshots across {len(event_dates)} dates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
