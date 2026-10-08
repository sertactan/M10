from __future__ import annotations

"""Phase14: controlled one-security adjusted-price & corporate-action import.

Defaults to read-only preview. Explicit --execute fetches an authorized price
source and saves adjusted bars in source-isolated Parquet, and optionally
Massive split/dividend event records. NEVER certifies delisting consideration,
historical PIT identity, dividend-total-return, WF9 or a canonical result.
"""
import argparse
import asyncio
from contextlib import closing
from datetime import date, datetime, timezone
import json
import math
import os
from pathlib import Path
import sqlite3
from uuid import uuid4

from app.bootstrap import AppContainer
from core.config.env import load_local_env
from core.contracts.entities import Security
from core.contracts.enums import Exchange
from core.prices.models import AdjustmentStatus
from data.providers.massive_price import MassivePriceProvider
from data.providers.marketparquet_price import MarketParquetPriceProvider
from data.providers.simfin_price import SimFinPriceProvider
from data.repositories.price_repository import PriceRepository
from data.storage.parquet_price_store import ParquetPriceStore

PROVIDERS = ("MASSIVE", "MARKETPARQUET", "SIMFIN")
SCHEMA = "MERIDYEN_PHASE14_PRICE_ACTIONS_PILOT_V1"


def actual_db(runtime_root: Path) -> Path:
    db = runtime_root / "data" / "runtime" / "operational.db"
    if not db.is_file() or db.is_symlink():
        raise ValueError("Existing M10 operational.db is required; new/empty DB forbidden")
    return db


def select_security(conn, ticker: str) -> dict:
    names = conn.execute(
        """SELECT security_id,ticker,name,exchange,active
           FROM security_master WHERE ticker=?
           AND market='US' AND exchange IN ('NASDAQ','NYSE','AMEX')
           ORDER BY security_id""",
        (ticker.upper(),),
    ).fetchall()
    if not names:
        raise ValueError("Ticker not found in real M10 US security_master")
    if len(names) != 1:
        raise ValueError(
            "Multiple historical security IDs for ticker; resolve CIK/listing identity manually"
        )
    return dict(names[0])


def make_provider(name: str):
    if name == "MASSIVE":
        return MassivePriceProvider()
    if name == "MARKETPARQUET":
        return MarketParquetPriceProvider(os.getenv("MARKETPARQUET_ROOT"))
    if name == "SIMFIN":
        return SimFinPriceProvider(os.getenv("SIMFIN_PRICE_BULK_PATH"))
    raise ValueError("Unsupported adjusted price source")


def validate_bars(bars, *, security_id: str, source: str, start: date, end: date) -> None:
    if not bars:
        raise ValueError("Provider returned no adjusted daily bars")
    seen = set()
    for bar in bars:
        if bar.security_id != security_id or bar.source != source:
            raise ValueError("Provider returned mixed security or source identity")
        if bar.trade_date in seen:
            raise ValueError("Duplicate trade date in price series")
        seen.add(bar.trade_date)
        if not start <= bar.trade_date <= end:
            raise ValueError("Price bar outside requested date window")
        if bar.adjustment_status in (AdjustmentStatus.UNKNOWN, AdjustmentStatus.RAW_ONLY):
            raise ValueError("Raw-only series cannot be imported as adjusted")
        if not math.isfinite(bar.raw_close) or not math.isfinite(bar.adjusted_close):
            raise ValueError("Nonfinite price")
        if bar.raw_close <= 0 or bar.adjusted_close <= 0:
            raise ValueError("Nonpositive price")
    # This is not completeness evidence: missing trading sessions, delisting
    # returns and re-used tickers are independently audited later.


def persist_report(report: dict, runtime_root: Path) -> Path:
    folder = runtime_root / "data" / "runtime" / "phase14_price_actions"
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / ("pilot_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                     + "_" + uuid4().hex[:8] + ".json")
    with dest.open("x", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return dest


async def pilot(
    *, runtime_root: Path, repo_root: Path, ticker: str,
    start: date, end: date, provider_name: str, execute: bool = False,
) -> dict:
    if end < start:
        raise ValueError("End date precedes start date")
    if provider_name not in PROVIDERS:
        raise ValueError("Only MASSIVE, MARKETPARQUET or SIMFIN adjusted inputs supported")
    runtime_root = runtime_root.expanduser().resolve()
    repo_root = repo_root.expanduser().resolve()
    db = actual_db(runtime_root)
    load_local_env(repo_root / ".env")
    with closing(sqlite3.connect(db.as_uri() + "?mode=ro", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        security = select_security(conn, ticker.upper())
    price_provider = make_provider(provider_name)
    actions_provider = MassivePriceProvider()
    report = {
        "schema": SCHEMA,
        "status": "READ_ONLY_PREVIEW",
        "ticker": ticker.upper(),
        "security_id": security["security_id"],
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "price_provider": provider_name,
        "price_provider_configured": bool(price_provider.configured),
        "corporate_actions_provider": "MASSIVE",
        "corporate_actions_provider_configured": bool(actions_provider.configured),
        "adjusted_price_bars_saved": 0,
        "splits_saved": 0,
        "dividends_saved": 0,
        "delisting_consideration_status": "NOT_AVAILABLE_UNVERIFIED",
        "historical_identity_pit_verified": False,
        "adjusted_price_completeness_verified": False,
        "total_return_dividend_reinvestment_verified": False,
        "wf9_activated": False,
    }
    if not execute:
        return report
    if not price_provider.configured:
        raise ValueError("Selected adjusted price provider is not configured")
    if not actions_provider.configured:
        raise ValueError(
            "Massive corporate actions not configured; cannot load both splits and dividends"
        )

    # Re-check the installed database and security identity before live writes.
    app = AppContainer(repo_root)
    if app.sqlite.path.resolve() != db:
        raise ValueError("Actual operational.db path differs from requested runtime root")
    app.initialize()
    try:
        verified = select_security(app.sqlite.connection, ticker.upper())
        if verified["security_id"] != security["security_id"]:
            raise ValueError("Security identity changed since read-only preview")
        sec = Security(
            security_id=security["security_id"], ticker=security["ticker"],
            name=security["name"], exchange=Exchange(security["exchange"]),
            active=bool(security["active"]),
        )
        # Gather all three feeds and validate BEFORE any database/Parquet write.
        bars = await price_provider.get_history(sec, start, end)
        validate_bars(bars, security_id=sec.security_id,
                      source=provider_name, start=start, end=end)
        splits = await actions_provider.get_splits(sec, start, end)
        dividends = await actions_provider.get_dividends(sec, start, end)
        if any(x.security_id != sec.security_id or x.source != "MASSIVE"
               or not start <= x.execution_date <= end or
               x.split_from <= 0 or x.split_to <= 0 for x in splits):
            raise ValueError("Invalid split records/identity in provider data")
        if any(x.security_id != sec.security_id or x.source != "MASSIVE"
               or not start <= x.ex_date <= end or
               not math.isfinite(x.cash_amount) or x.cash_amount < 0
               for x in dividends):
            raise ValueError("Invalid dividend records/identity in provider data")

        repository = PriceRepository(
            app.sqlite, ParquetPriceStore(app.resolve_data_path(app.app_config.database.parquet_root))
        )
        desc = repository.save_series(bars)
        # This is intentionally NOT BACKTEST_ADJUSTED until PIT identity,
        # corporate actions, delisting and independent coverage are audited.
        repository.select_series(
            security_id=sec.security_id, start=desc.start_date, end=desc.end_date,
            source=desc.source, source_symbol=desc.source_symbol,
            purpose="PHASE14_ADJUSTED_PILOT_UNVERIFIED",
            reason="partial adjusted series; delisting/PIT identity unverified",
        )
        n_split = repository.save_splits(splits)
        n_div = repository.save_dividends(dividends)
        report.update({
            "status": "PARTIAL_IMPORTED_DELISTING_AND_PIT_UNVERIFIED",
            "adjusted_price_bars_saved": len(bars),
            "splits_saved": n_split,
            "dividends_saved": n_div,
            "price_series_first": desc.start_date.isoformat(),
            "price_series_last": desc.end_date.isoformat(),
            "source_adjustment_status": desc.adjustment_status.value,
        })
        report["report_path"] = str(persist_report(report, runtime_root))
        return report
    finally:
        app.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--start", type=date.fromisoformat, default=date(2013, 1, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=date(2024, 12, 31))
    parser.add_argument("--provider", choices=PROVIDERS, default="MASSIVE")
    parser.add_argument("--runtime-root", type=Path,
                        default=Path(os.getenv("S153_RUNTIME_ROOT", ".")))
    parser.add_argument("--execute", action="store_true",
                        help="Opt in to provider requests and real local DB/Parquet writes")
    args = parser.parse_args()
    try:
        result = asyncio.run(pilot(
            runtime_root=args.runtime_root,
            repo_root=Path(__file__).resolve().parents[1],
            ticker=args.ticker, start=args.start, end=args.end,
            provider_name=args.provider, execute=args.execute,
        ))
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
        parser.exit(2, "PHASE14_PRICE_ACTIONS_BLOCKED: " + type(exc).__name__ + ": " + str(exc) + "\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] != "READ_ONLY_PREVIEW" or result["price_provider_configured"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
