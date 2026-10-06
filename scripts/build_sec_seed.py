from __future__ import annotations

import argparse
import asyncio
import csv
from datetime import date
from pathlib import Path

from data.providers.sec_edgar_universe import SECEdgarUniverseProvider


DEFAULT_USER_AGENT = (
    "S15.3 Research Terminal seed builder "
    "(https://github.com/sertactan/M10)"
)


async def build(output: Path, user_agent: str) -> int:
    provider = SECEdgarUniverseProvider(user_agent=user_agent)
    records = await provider.list_current_us_securities()
    output.parent.mkdir(parents=True, exist_ok=True)

    snapshot = date.today().isoformat()
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "snapshot_date",
                "ticker",
                "name",
                "exchange",
                "exchange_mic",
                "cik",
            ],
        )
        writer.writeheader()
        for record in sorted(
            records,
            key=lambda item: (item.exchange.value, item.ticker, item.name),
        ):
            writer.writerow(
                {
                    "snapshot_date": snapshot,
                    "ticker": record.ticker,
                    "name": record.name,
                    "exchange": record.exchange.value,
                    "exchange_mic": record.exchange_mic,
                    "cik": record.cik or "",
                }
            )
    return len(records)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default="data/seeds/sec_us_current.csv",
    )
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    args = parser.parse_args()
    count = asyncio.run(build(Path(args.output), args.user_agent))
    print(f"SEC seed rows: {count}")
    if count < 1000:
        raise SystemExit("SEC seed unexpectedly small")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
