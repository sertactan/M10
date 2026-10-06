from __future__ import annotations

import argparse
import asyncio
import csv
import io
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import httpx


BASE = "https://raw.githubusercontent.com/JerBouma/FinanceDatabase/main/database"

MARKETS = {
    "JP": {
        "exchange": "JPX",
        "mic": "XJPX",
        "country": "Japan",
        "suffix": ".T",
        "files": (
            ("Equity", f"{BASE}/equities/JPX.csv"),
            ("ETF", f"{BASE}/etfs/JPX.csv"),
        ),
        "minimum_rows": 3000,
    },
    "TR": {
        "exchange": "BIST",
        "mic": "XIST",
        "country": "Turkey",
        "suffix": ".IS",
        "files": (
            ("Equity", f"{BASE}/equities/IST.csv"),
            ("ETF", f"{BASE}/etfs/IST.csv"),
        ),
        "minimum_rows": 300,
    },
    "HK": {
        "exchange": "HKEX",
        "mic": "XHKG",
        "country": "Hong Kong",
        "suffix": ".HK",
        "files": (
            ("Equity", f"{BASE}/equities/HKG.csv"),
            ("ETF", f"{BASE}/etfs/HKG.csv"),
        ),
        "minimum_rows": 1500,
    },
}


@dataclass(frozen=True)
class SeedRow:
    snapshot_date: str
    market: str
    exchange: str
    mic: str
    ticker: str
    source_symbol: str
    name: str
    asset_type: str
    currency: str
    country: str
    country_code: str
    isin: str
    sector: str
    industry: str
    figi: str
    composite_figi: str
    shareclass_figi: str
    source: str
    source_scope: str
    redistribution_status: str


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _canonical_ticker(symbol: str, suffix: str) -> str:
    text = symbol.strip().upper()
    if suffix and text.endswith(suffix.upper()):
        text = text[: -len(suffix)]
    return text


def parse_financedatabase_csv(
    text: str,
    *,
    market: str,
    exchange: str,
    mic: str,
    country: str,
    suffix: str,
    asset_type: str,
    snapshot_date: str,
) -> list[SeedRow]:
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None or not {"symbol", "name"}.issubset(reader.fieldnames):
        raise ValueError(f"Unexpected FinanceDatabase columns: {reader.fieldnames}")

    out: list[SeedRow] = []
    for row in reader:
        if _truthy(row.get("delisted")):
            continue
        source_symbol = (row.get("symbol") or "").strip().upper()
        ticker = _canonical_ticker(source_symbol, suffix)
        name = (row.get("name") or "").strip()
        if not ticker or not name:
            continue

        row_mic = (row.get("mic") or "").strip().upper() or mic
        row_currency = (row.get("currency") or "").strip().upper()
        row_country = (row.get("country") or "").strip() or country
        sector = (row.get("sector") or row.get("category_group") or "").strip()
        industry = (
            row.get("industry")
            or row.get("category")
            or row.get("industry_group")
            or ""
        ).strip()

        out.append(
            SeedRow(
                snapshot_date=snapshot_date,
                market=market,
                exchange=exchange,
                mic=row_mic,
                ticker=ticker,
                source_symbol=source_symbol,
                name=name,
                asset_type=asset_type,
                currency=row_currency,
                country=row_country,
                country_code=market,
                isin=(row.get("isin") or "").strip().upper(),
                sector=sector,
                industry=industry,
                figi=(row.get("figi") or "").strip().upper(),
                composite_figi=(row.get("composite_figi") or "").strip().upper(),
                shareclass_figi=(row.get("shareclass_figi") or "").strip().upper(),
                source="FINANCEDATABASE_MIT_REFERENCE",
                source_scope="REFERENCE_ONLY",
                redistribution_status="MIT_REFERENCE_REQUIRES_SOURCE_POLICY",
            )
        )
    return out


async def _fetch_text(client: httpx.AsyncClient, url: str) -> str:
    response = await client.get(
        url,
        headers={"User-Agent": "S15.3-Research-Terminal/2C market-seed-builder"},
    )
    response.raise_for_status()
    return response.text


async def build(output: Path) -> dict[str, int]:
    snapshot = date.today().isoformat()
    combined: list[SeedRow] = []
    counts: dict[str, int] = {}

    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        for market, cfg in MARKETS.items():
            market_rows: list[SeedRow] = []
            for asset_type, url in cfg["files"]:
                text = await _fetch_text(client, url)
                market_rows.extend(
                    parse_financedatabase_csv(
                        text,
                        market=market,
                        exchange=str(cfg["exchange"]),
                        mic=str(cfg["mic"]),
                        country=str(cfg["country"]),
                        suffix=str(cfg["suffix"]),
                        asset_type=asset_type,
                        snapshot_date=snapshot,
                    )
                )

            # listing identity is market/exchange/ticker/asset-type. Keep the first
            # occurrence deterministically if an upstream file contains duplicates.
            deduped: dict[tuple[str, str, str, str], SeedRow] = {}
            for row in market_rows:
                key = (row.market, row.exchange, row.ticker, row.asset_type)
                deduped.setdefault(key, row)
            market_rows = list(deduped.values())

            minimum = int(cfg["minimum_rows"])
            if len(market_rows) < minimum:
                raise RuntimeError(
                    f"{market} embedded reference seed unexpectedly small: "
                    f"{len(market_rows)} < {minimum}"
                )
            counts[market] = len(market_rows)
            combined.extend(market_rows)

    output.parent.mkdir(parents=True, exist_ok=True)
    fields = list(SeedRow.__dataclass_fields__)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in sorted(
            combined,
            key=lambda x: (x.market, x.exchange, x.asset_type, x.ticker),
        ):
            writer.writerow({field: getattr(row, field) for field in fields})

    return counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default="data/seeds/jp_tr_hk_current.csv",
    )
    args = parser.parse_args()
    counts = asyncio.run(build(Path(args.output)))
    print("Embedded reference seed counts:")
    for market in ("JP", "TR", "HK"):
        print(f"  {market}: {counts.get(market, 0)}")
    print(f"  TOTAL: {sum(counts.values())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
