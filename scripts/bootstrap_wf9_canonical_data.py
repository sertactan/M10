from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path

from app.bootstrap import AppContainer
from core.contracts.entities import Security
from core.contracts.enums import Exchange
from core.prices.engine import HistoricalPriceEngine
from data.providers.marketparquet_price import MarketParquetPriceProvider
from data.providers.massive_price import MassivePriceProvider
from data.providers.simfin_price import SimFinPriceProvider
from data.providers.stooq_price import StooqPriceProvider
from data.providers.yahoo_price import YahooCompatiblePriceProvider
from data.repositories.price_repository import PriceRepository
from data.repositories.provider_health_repository import ProviderHealthRepository
from data.storage.parquet_price_store import ParquetPriceStore
from scripts.sync_free_pit_universe import run as sync_pit_universe


@dataclass(frozen=True)
class WF9PriceTarget:
    security_id: str
    ticker: str
    name: str
    exchange: str
    first_snapshot: date
    last_snapshot: date


@dataclass(frozen=True)
class WF9BootstrapReport:
    start_date: date
    end_date: date
    requested_snapshots: int
    existing_snapshot_dates: int
    target_securities: int
    price_complete: int
    price_failed: int
    provider: str
    status: str
    failures: tuple[str, ...]


def _month_count(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + end.month - start.month + 1


def _targets(app: AppContainer, start: date, end: date) -> list[WF9PriceTarget]:
    rows = app.sqlite.connection.execute(
        """
        SELECT
            usm.security_id,
            MAX(usm.ticker) AS ticker,
            MAX(sm.name) AS name,
            MAX(usm.exchange) AS exchange,
            MIN(usm.snapshot_date) AS first_snapshot,
            MAX(usm.snapshot_date) AS last_snapshot
        FROM universe_snapshot_membership usm
        JOIN security_master sm ON sm.security_id=usm.security_id
        WHERE usm.snapshot_date BETWEEN ? AND ?
          AND usm.exchange IN ('NASDAQ','NYSE','AMEX')
        GROUP BY usm.security_id
        ORDER BY usm.security_id
        """,
        (start.isoformat(), end.isoformat()),
    ).fetchall()
    return [
        WF9PriceTarget(
            security_id=str(row["security_id"]),
            ticker=str(row["ticker"]),
            name=str(row["name"]),
            exchange=str(row["exchange"]),
            first_snapshot=date.fromisoformat(str(row["first_snapshot"])),
            last_snapshot=date.fromisoformat(str(row["last_snapshot"])),
        )
        for row in rows
    ]


def _existing_snapshot_dates(app: AppContainer, start: date, end: date) -> int:
    row = app.sqlite.connection.execute(
        """
        SELECT COUNT(DISTINCT snapshot_date) AS n
        FROM universe_snapshot_membership
        WHERE snapshot_date BETWEEN ? AND ?
          AND exchange IN ('NASDAQ','NYSE','AMEX')
        """,
        (start.isoformat(), end.isoformat()),
    ).fetchone()
    return int(row["n"] if row is not None else 0)


def _already_covered(app: AppContainer, target: WF9PriceTarget) -> bool:
    """Return true only when canonical prices span the security's PIT membership window.

    A stock is not required to have bars before its IPO or after delisting.
    Requiring the global WF9 price window would force impossible coverage for
    legitimate historical names; checking the actual first/last PIT membership
    dates is the fail-closed condition relevant to WF9 readiness.
    """
    row = app.sqlite.connection.execute(
        """
        SELECT 1
        FROM canonical_price_selection
        WHERE security_id=?
          AND purpose IN ('BACKTEST_ADJUSTED','BACKTEST')
          AND start_date<=?
          AND end_date>=?
        LIMIT 1
        """,
        (
            target.security_id,
            target.first_snapshot.isoformat(),
            target.last_snapshot.isoformat(),
        ),
    ).fetchone()
    return row is not None


def _security(target: WF9PriceTarget) -> Security:
    return Security(
        security_id=target.security_id,
        ticker=target.ticker,
        name=target.name,
        exchange=Exchange(target.exchange),
        active=target.last_snapshot >= date.today(),
    )


async def _sync_prices(
    app: AppContainer,
    targets: list[WF9PriceTarget],
    *,
    start_date: date,
    end_date: date,
    provider: str,
    concurrency: int,
    limit: int | None,
) -> tuple[int, list[str]]:
    parquet = ParquetPriceStore(
        app.resolve_data_path(app.app_config.database.parquet_root)
    )
    repo = PriceRepository(app.sqlite, parquet)
    providers = {
        "MASSIVE": MassivePriceProvider(),
        "MARKETPARQUET": MarketParquetPriceProvider(os.getenv("MARKETPARQUET_ROOT")),
        "SIMFIN": SimFinPriceProvider(os.getenv("SIMFIN_PRICE_BULK_PATH")),
        "STOOQ": StooqPriceProvider(),
        "YAHOO_COMPAT": YahooCompatiblePriceProvider(),
    }
    engine = HistoricalPriceEngine(
        repo,
        providers,
        ProviderHealthRepository(app.sqlite),
        default_provider_concurrency=max(1, concurrency),
    )

    # 400 calendar days before the first PIT observation supports long price
    # features; 400 after the last observation covers the 252-session label.
    price_start = start_date - timedelta(days=400)
    price_end = end_date + timedelta(days=400)
    selected_targets = targets[:limit] if limit else targets
    semaphore = asyncio.Semaphore(max(1, concurrency))
    complete = 0
    failures: list[str] = []

    async def one(index: int, target: WF9PriceTarget) -> None:
        nonlocal complete
        if _already_covered(app, target):
            complete += 1
            print(f"PRICE SKIP {index}/{len(selected_targets)} {target.ticker}: already canonical")
            return
        async with semaphore:
            try:
                selection = await engine.sync_history(
                    _security(target),
                    price_start,
                    price_end,
                    require_adjusted=True,
                    provider=provider,
                    validate_with_fallback=False,
                )
                complete += 1
                print(
                    f"PRICE OK {index}/{len(selected_targets)} {target.ticker}: "
                    f"{selection.source}"
                )
            except Exception as exc:
                message = f"{target.security_id}|{target.ticker}: {exc}"
                failures.append(message)
                print(f"PRICE FAIL {index}/{len(selected_targets)} {target.ticker}: {exc}")

    await asyncio.gather(
        *(one(index, target) for index, target in enumerate(selected_targets, start=1))
    )
    return complete, failures


async def run(
    *,
    start_date: date,
    end_date: date,
    provider: str,
    concurrency: int,
    sync_universe: bool,
    limit: int | None,
    output: Path,
) -> WF9BootstrapReport:
    if end_date < start_date:
        raise ValueError("end_date must be >= start_date")

    root = Path(__file__).resolve().parents[1]

    if sync_universe:
        universe_code = await sync_pit_universe(start_date, end_date)
        if universe_code not in (0,):
            raise RuntimeError(
                "PIT universe bootstrap stopped before completion. Re-run the command "
                "after the provider rate-limit resets; completed snapshots are resumable."
            )

    app = AppContainer(root)
    app.initialize()
    try:
        targets = _targets(app, start_date, end_date)
        snapshots = _existing_snapshot_dates(app, start_date, end_date)
        expected_snapshots = _month_count(start_date, end_date)
        if snapshots != expected_snapshots:
            raise RuntimeError(
                f"WF9 requires {expected_snapshots} exact monthly PIT snapshots; "
                f"database has {snapshots}. Run with --sync-universe and a configured "
                "ALPHAVANTAGE_API_KEY or MASSIVE_API_KEY (or import an equivalent "
                "PIT-capable archive)."
            )
        if not targets:
            raise RuntimeError("WF9 PIT universe is empty")

        complete, failures = await _sync_prices(
            app,
            targets,
            start_date=start_date,
            end_date=end_date,
            provider=provider,
            concurrency=concurrency,
            limit=limit,
        )
        requested_targets = len(targets[:limit] if limit else targets)
        status = "COMPLETE" if complete == requested_targets and not failures else "INCOMPLETE"
        report = WF9BootstrapReport(
            start_date=start_date,
            end_date=end_date,
            requested_snapshots=expected_snapshots,
            existing_snapshot_dates=snapshots,
            target_securities=requested_targets,
            price_complete=complete,
            price_failed=len(failures),
            provider=provider,
            status=status,
            failures=tuple(failures),
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(asdict(report), indent=2, default=str, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return report
    finally:
        app.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bootstrap exact PIT universe + canonical adjusted prices for WF9"
    )
    parser.add_argument("--start", default="2013-01-01")
    parser.add_argument("--end", default="2024-12-31")
    parser.add_argument(
        "--provider",
        default="AUTO",
        choices=("AUTO", "MASSIVE", "MARKETPARQUET", "SIMFIN"),
        help="Authoritative adjusted source. Yahoo/Stooq RAW_ONLY cannot be forced.",
    )
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--sync-universe", action="store_true")
    parser.add_argument("--limit", type=int, help="Development-only target cap")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/runtime/wf9_bootstrap_report.json"),
    )
    args = parser.parse_args()

    report = asyncio.run(
        run(
            start_date=date.fromisoformat(args.start),
            end_date=date.fromisoformat(args.end),
            provider=args.provider,
            concurrency=max(1, args.concurrency),
            sync_universe=args.sync_universe,
            limit=args.limit,
            output=args.output,
        )
    )
    print(json.dumps(asdict(report), indent=2, default=str, sort_keys=True))
    return 0 if report.status == "COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
