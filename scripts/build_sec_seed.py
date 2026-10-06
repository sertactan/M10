from __future__ import annotations

import argparse
import asyncio
import csv
from datetime import date, datetime, time, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile

import httpx
import pandas as pd

from core.universe.identity import EXCHANGE_TO_MIC, exchange_from_sec_name, normalize_cik
from core.universe.models import UniverseRecord
from data.providers.sec_edgar_universe import SECEdgarUniverseProvider


DEFAULT_USER_AGENT = (
    "S15.3 Research Terminal seed builder "
    "(https://github.com/sertactan/M10)"
)

# Shared CI runners can occasionally receive SEC 403s. This clean mirror is
# generated from SEC's official company_tickers_exchange.json and is used only
# as a build-time fallback; the installed app still refreshes from SEC directly.
EDGARTOOLS_PARQUET = (
    "https://raw.githubusercontent.com/dgunning/edgartools/main/"
    "edgar/reference/data/company_tickers.parquet"
)
EDGARTOOLS_SNAPSHOT_DATE = date(2026, 6, 1)


async def _records_from_sec(user_agent: str) -> tuple[list[UniverseRecord], date, str]:
    provider = SECEdgarUniverseProvider(user_agent=user_agent)
    rows = await provider.list_current_us_securities()
    return rows, date.today(), "SEC_DIRECT"


async def _records_from_edgartools_mirror() -> tuple[list[UniverseRecord], date, str]:
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        response = await client.get(
            EDGARTOOLS_PARQUET,
            headers={"User-Agent": DEFAULT_USER_AGENT},
        )
        response.raise_for_status()
        payload = response.content

    with NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
        tmp.write(payload)
        tmp_path = Path(tmp.name)

    try:
        frame = pd.read_parquet(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    required = {"cik", "ticker", "exchange", "name"}
    if not required.issubset(set(frame.columns)):
        raise RuntimeError(
            f"Unexpected edgartools fallback schema: {list(frame.columns)}"
        )

    availability = datetime.combine(
        EDGARTOOLS_SNAPSHOT_DATE,
        time.min,
        tzinfo=timezone.utc,
    )
    records: list[UniverseRecord] = []
    for row in frame.to_dict(orient="records"):
        exchange = exchange_from_sec_name(
            None if pd.isna(row.get("exchange")) else str(row.get("exchange"))
        )
        if exchange is None:
            continue
        ticker = str(row.get("ticker") or "").strip().upper()
        name = str(row.get("name") or "").strip()
        if not ticker or not name:
            continue
        records.append(
            UniverseRecord(
                ticker=ticker,
                name=name,
                exchange=exchange,
                exchange_mic=EXCHANGE_TO_MIC[exchange],
                active=True,
                provider="SEC_EDGAR",
                availability_date=availability,
                security_type=None,
                cik=normalize_cik(row.get("cik")),
                currency="USD",
                locale="us",
            )
        )
    return records, EDGARTOOLS_SNAPSHOT_DATE, "SEC_MIRROR_EDGARTOOLS"


async def build(output: Path, user_agent: str) -> int:
    try:
        records, snapshot_date, transport = await _records_from_sec(user_agent)
    except Exception as exc:
        print(f"SEC direct seed fetch failed: {exc}")
        print("Using clean SEC-derived edgartools mirror fallback.")
        records, snapshot_date, transport = await _records_from_edgartools_mirror()

    output.parent.mkdir(parents=True, exist_ok=True)
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
                "transport",
            ],
        )
        writer.writeheader()
        for record in sorted(
            records,
            key=lambda item: (item.exchange.value, item.ticker, item.name),
        ):
            writer.writerow(
                {
                    "snapshot_date": snapshot_date.isoformat(),
                    "ticker": record.ticker,
                    "name": record.name,
                    "exchange": record.exchange.value,
                    "exchange_mic": record.exchange_mic,
                    "cik": record.cik or "",
                    "transport": transport,
                }
            )
    print(f"SEC seed transport: {transport}")
    print(f"SEC seed snapshot: {snapshot_date.isoformat()}")
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
