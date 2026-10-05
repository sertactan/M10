from __future__ import annotations

import argparse
import asyncio
import os
from datetime import date
from pathlib import Path

from app.bootstrap import AppContainer
from core.contracts.entities import Security
from core.contracts.enums import Exchange
from core.prices.engine import HistoricalPriceEngine
from core.universe.service import USUniverseService
from data.providers.finnhub_universe import FinnhubUniverseProvider
from data.providers.marketparquet_price import MarketParquetPriceProvider
from data.providers.massive_price import MassivePriceProvider
from data.providers.massive_universe import MassiveUniverseProvider
from data.providers.sec_edgar_universe import SECEdgarUniverseProvider
from data.providers.simfin_price import SimFinPriceProvider
from data.providers.stooq_price import StooqPriceProvider
from data.providers.yahoo_price import YahooCompatiblePriceProvider
from data.repositories.price_repository import PriceRepository
from data.repositories.security_repository import SecurityRepository
from data.storage.parquet_price_store import ParquetPriceStore


def doctor(root: Path) -> int:
    app = AppContainer(root)
    app.initialize()
    print(f"APP: {app.app_config.app_name}")
    print(f"MARKET: {app.app_config.market}")
    print(f"PIT: {'STRICT' if app.app_config.strict_pit else 'OFF'}")
    print(f"MOCK DATA: {'FORBIDDEN' if not app.app_config.allow_mock_data else 'ENABLED'}")
    print(f"V1.2: {app.v12_config.status}")
    print(f"V1.4: {app.v14_config.status}")
    print(f"SQLite: {app.sqlite.db_path}")
    app.close()
    return 0


def _security_from_row(row) -> Security:
    return Security(
        security_id=row["security_id"],
        ticker=row["ticker"],
        name=row["name"],
        exchange=Exchange(row["exchange"]),
        cik=row["cik"],
        sector=row["sector"],
        industry=row["industry"],
        ipo_date=date.fromisoformat(row["ipo_date"]) if row["ipo_date"] else None,
        delisted_date=date.fromisoformat(row["delisted_date"]) if row["delisted_date"] else None,
        active=bool(row["active"]),
    )


async def sync_universe(root: Path, as_of: date, include_delisted: bool, ticker_events: int) -> int:
    app = AppContainer(root)
    app.initialize()
    try:
        service = USUniverseService(
            SecurityRepository(app.sqlite),
            sec=SECEdgarUniverseProvider(),
            massive=MassiveUniverseProvider(),
            finnhub=FinnhubUniverseProvider(),
        )
        result = await service.sync(
            as_of=as_of,
            include_delisted=include_delisted,
            ticker_event_limit=ticker_events,
        )
        print(f"SOURCE MODE: {result.source_mode}")
        print(f"AS OF: {result.as_of}")
        print(f"ACTIVE LOADED: {result.active_loaded}")
        print(f"DELISTED LOADED: {result.delisted_loaded}")
        print(f"SEC ENRICHED: {result.sec_enriched}")
        print(f"FINNHUB VALIDATED: {result.finnhub_validated}")
        print(f"SNAPSHOT COUNT: {result.snapshot_count}")
        print(f"TICKER EVENTS: {result.ticker_events_loaded}")
        return 0
    finally:
        app.close()


async def sync_price(root: Path, ticker: str, start: date, end: date, provider: str) -> int:
    app = AppContainer(root)
    app.initialize()
    try:
        row = app.sqlite.connection.execute(
            "SELECT * FROM security_master WHERE ticker=? ORDER BY active DESC, updated_at DESC LIMIT 1",
            (ticker.upper(),),
        ).fetchone()
        if row is None:
            raise RuntimeError(f"Ticker not found in security_master: {ticker}. Run --sync-universe first.")
        security = _security_from_row(row)
        parquet = ParquetPriceStore(root / app.app_config.database.parquet_root)
        repo = PriceRepository(app.sqlite, parquet)
        providers = {
            "MASSIVE": MassivePriceProvider(),
            "STOOQ": StooqPriceProvider(),
            "SIMFIN": SimFinPriceProvider(os.getenv("SIMFIN_PRICE_BULK_PATH")),
            "YAHOO_COMPAT": YahooCompatiblePriceProvider(),
            "MARKETPARQUET": MarketParquetPriceProvider(os.getenv("MARKETPARQUET_ROOT")),
        }
        selection = await HistoricalPriceEngine(repo, providers).sync_history(
            security, start, end, provider=provider, require_adjusted=True
        )
        selected = repo.series_for_window(security.security_id, start, end)
        print(f"TICKER: {ticker.upper()}")
        print(f"WINDOW: {start} .. {end}")
        print(f"SELECTED SOURCE: {selection.source}")
        print(f"SOURCE SYMBOL: {selection.source_symbol}")
        print(f"SERIES AVAILABLE: {len(selected)}")
        return 0
    finally:
        app.close()


def ingest_stooq_bulk(root: Path, zip_path: str) -> int:
    app = AppContainer(root)
    app.initialize()
    try:
        security_repo = SecurityRepository(app.sqlite)
        price_repo = PriceRepository(
            app.sqlite, ParquetPriceStore(root / app.app_config.database.parquet_root)
        )
        provider = StooqPriceProvider()
        count=0
        series_count=0
        for group in provider.iter_bulk_zip_series(
            zip_path,
            security_lookup=lambda t: security_repo.lookup_security_id(ticker=t),
        ):
            price_repo.save_series(group)
            count += len(group)
            series_count += 1
        print(f"STOOQ BULK BARS STORED: {count}")
        print(f"SERIES: {series_count}")
        return 0
    finally:
        app.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="S15.3 Research Terminal")
    parser.add_argument("--doctor", action="store_true", help="Validate architecture")
    parser.add_argument("--sync-universe", action="store_true", help="Sync US universe")
    parser.add_argument("--as-of", help="Universe PIT date YYYY-MM-DD; default=today")
    parser.add_argument("--no-delisted", action="store_true", help="Skip current delisted archive sync")
    parser.add_argument("--ticker-events", type=int, default=0, help="Fetch ticker-change events for first N securities")
    parser.add_argument("--sync-price", metavar="TICKER", help="Sync one ticker's historical daily prices")
    parser.add_argument("--price-start", help="Price start YYYY-MM-DD")
    parser.add_argument("--price-end", help="Price end YYYY-MM-DD")
    parser.add_argument("--price-provider", default="AUTO", help="AUTO/MASSIVE/STOOQ/SIMFIN/YAHOO_COMPAT/MARKETPARQUET")
    parser.add_argument("--ingest-stooq-bulk", metavar="ZIP", help="Bootstrap local Stooq bulk ZIP into Parquet")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    if args.doctor:
        return doctor(root)
    if args.sync_universe:
        as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
        return asyncio.run(sync_universe(root, as_of, not args.no_delisted, args.ticker_events))
    if args.sync_price:
        if not args.price_start or not args.price_end:
            parser.error("--sync-price requires --price-start and --price-end")
        return asyncio.run(sync_price(
            root, args.sync_price, date.fromisoformat(args.price_start),
            date.fromisoformat(args.price_end), args.price_provider,
        ))
    if args.ingest_stooq_bulk:
        return ingest_stooq_bulk(root, args.ingest_stooq_bulk)
    print("UI NOT IMPLEMENTED — Phase 9")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
