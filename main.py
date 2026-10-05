from __future__ import annotations

import argparse
import asyncio
from datetime import date
from pathlib import Path

from app.bootstrap import AppContainer
from core.universe.service import USUniverseService
from data.providers.finnhub_universe import FinnhubUniverseProvider
from data.providers.massive_universe import MassiveUniverseProvider
from data.providers.sec_edgar_universe import SECEdgarUniverseProvider
from data.repositories.security_repository import SecurityRepository


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


def main() -> int:
    parser = argparse.ArgumentParser(description="S15.3 Research Terminal")
    parser.add_argument("--doctor", action="store_true", help="Validate architecture")
    parser.add_argument("--sync-universe", action="store_true", help="Sync US universe")
    parser.add_argument("--as-of", help="Universe PIT date YYYY-MM-DD; default=today")
    parser.add_argument("--no-delisted", action="store_true", help="Skip current delisted archive sync")
    parser.add_argument(
        "--ticker-events",
        type=int,
        default=0,
        help="Fetch ticker-change events for the first N current common stocks (incremental)",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    if args.doctor:
        return doctor(root)
    if args.sync_universe:
        as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
        return asyncio.run(sync_universe(root, as_of, not args.no_delisted, args.ticker_events))
    print("UI NOT IMPLEMENTED — Phase 9")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
