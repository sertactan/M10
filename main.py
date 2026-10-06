from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import date, datetime, time, timezone
from pathlib import Path

from app.bootstrap import AppContainer
from core.contracts.entities import Security
from core.contracts.enums import Exchange
from core.fundamentals.engine import FundamentalEngine
from core.fundamentals.snapshot import FundamentalSnapshotService
from core.features.s153_v12_input_loader import S153V12InputLoader
from core.models.s153_v12 import S153V12Model
from core.prices.engine import HistoricalPriceEngine
from core.runtime.readiness import check_release_readiness
from core.universe.service import USUniverseService
from data.providers.company_ir import CompanyInvestorRelationsProvider
from data.providers.adanos_global_reference import AdanosGlobalReferenceProvider
from data.providers.finnhub_fundamentals import FinnhubFundamentalsProvider
from data.providers.finnhub_universe import FinnhubUniverseProvider
from data.providers.fmp_fundamentals import FMPFundamentalsProvider
from data.providers.marketparquet_price import MarketParquetPriceProvider
from data.providers.massive_price import MassivePriceProvider
from data.providers.massive_universe import MassiveUniverseProvider
from data.providers.sec_edgar_fundamentals import SECEdgarFundamentalsProvider
from data.providers.sec_edgar_universe import SECEdgarUniverseProvider
from data.providers.simfin_fundamentals import SimFinFundamentalsProvider
from data.providers.simfin_price import SimFinPriceProvider
from data.providers.stooq_price import StooqPriceProvider
from data.providers.yahoo_price import YahooCompatiblePriceProvider
from data.repositories.fundamental_repository import FundamentalRepository
from data.repositories.global_security_repository import GlobalSecurityRepository
from data.repositories.model_feature_repository import ModelFeatureRepository
from data.repositories.model_run_repository import ModelRunRepository
from data.repositories.price_repository import PriceRepository
from data.repositories.provider_health_repository import ProviderHealthRepository
from data.repositories.security_repository import SecurityRepository
from data.repositories.validation_repository import ValidationRepository
from data.storage.parquet_price_store import ParquetPriceStore


def doctor(root: Path) -> int:
    app = AppContainer(root)
    app.initialize()
    try:
        readiness = check_release_readiness(root)
        print(f"APP: {app.app_config.app_name}")
        print(f"MARKET: {app.app_config.market}")
        print(f"PIT: {'STRICT' if app.app_config.strict_pit else 'OFF'}")
        print(f"MOCK DATA: {'FORBIDDEN' if not app.app_config.allow_mock_data else 'ENABLED'}")
        print(f"V1.2: {app.v12_config.status}")
        print(f"V1.4 legacy: {app.v14_config.status}")\n        print(f"V1.4.1 production: {app.v141_config.status}")
        print(f"SQLite: {app.sqlite.db_path}")
        print(f"RUNTIME ROOT: {app.runtime_root}")
        print("RUNTIME WRITABLE: YES")
        print(
            "OFFLINE SECURITY MASTER: "
            + ", ".join(
                f"{market}={count}"
                for market, count in sorted(app.bootstrap_counts.items())
            )
        )
        if app.sqlite.last_recovery_backup is not None:
            print(f"SQLITE RECOVERED FROM: {app.sqlite.last_recovery_backup}")
        else:
            print("SQLITE RECOVERY: NOT NEEDED")
        print(f"RELEASE READY: {'YES' if readiness.ready else 'NO'}")
        if readiness.blockers:
            print("BLOCKERS: " + ", ".join(readiness.blockers))
        return 0 if readiness.ready else 1
    finally:
        app.close()


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


def _load_security(app: AppContainer, ticker: str) -> Security:
    row = app.sqlite.connection.execute(
        "SELECT * FROM security_master WHERE ticker=? ORDER BY active DESC, updated_at DESC LIMIT 1",
        (ticker.upper(),),
    ).fetchone()
    if row is None:
        raise RuntimeError(f"Ticker not found in security_master: {ticker}. Run --sync-universe first.")
    return _security_from_row(row)


async def sync_universe(root: Path, as_of: date, include_delisted: bool, ticker_events: int) -> int:
    app = AppContainer(root)
    app.initialize()
    try:
        service = USUniverseService(
            SecurityRepository(app.sqlite),
            sec=SECEdgarUniverseProvider(
                mirror_root=app.resolve_data_path("sec_mirror")
            ),
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


async def sync_global_reference(root: Path, market: str | None = None) -> int:
    app = AppContainer(root)
    app.initialize()
    try:
        health = ProviderHealthRepository(app.sqlite)
        provider_name = "ADANOS_REFERENCE"
        if not health.can_attempt(provider_name):
            raise RuntimeError("ADANOS_REFERENCE circuit is open")

        provider = AdanosGlobalReferenceProvider()
        started = __import__("time").perf_counter()
        try:
            records = await provider.list_reference_securities()
            if market:
                wanted = market.strip().upper()
                records = [row for row in records if row.market.upper() == wanted]
            count = GlobalSecurityRepository(app.sqlite).bulk_upsert_reference(records)
            health.record_success(
                provider_name,
                latency_ms=(__import__("time").perf_counter() - started) * 1000.0,
            )
        except Exception as exc:
            text = str(exc)
            health.record_failure(
                provider_name,
                latency_ms=(__import__("time").perf_counter() - started) * 1000.0,
                rate_limited=("429" in text or "rate limit" in text.lower()),
                message=text[:500],
            )
            raise

        counts = GlobalSecurityRepository(app.sqlite).count_by_market()
        print(f"GLOBAL REFERENCE LOADED: {count}")
        if market:
            print(f"MARKET: {market.upper()} · ROWS: {counts.get(market.upper(), 0)}")
        else:
            top = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:15]
            print("TOP MARKETS: " + ", ".join(f"{key}={value}" for key, value in top))
        print("SCOPE: REFERENCE_ONLY (not authoritative model evidence)")
        return 0
    finally:
        app.close()


async def sync_price(root: Path, ticker: str, start: date, end: date, provider: str) -> int:
    app = AppContainer(root)
    app.initialize()
    try:
        security = _load_security(app, ticker)
        parquet = ParquetPriceStore(app.resolve_data_path(app.app_config.database.parquet_root))
        repo = PriceRepository(app.sqlite, parquet)
        providers = {
            "MASSIVE": MassivePriceProvider(),
            "STOOQ": StooqPriceProvider(),
            "SIMFIN": SimFinPriceProvider(os.getenv("SIMFIN_PRICE_BULK_PATH")),
            "YAHOO_COMPAT": YahooCompatiblePriceProvider(),
            "MARKETPARQUET": MarketParquetPriceProvider(os.getenv("MARKETPARQUET_ROOT")),
        }
        selection = await HistoricalPriceEngine(repo, providers, ProviderHealthRepository(app.sqlite)).sync_history(
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


async def sync_fundamentals(root: Path, ticker: str, provider: str) -> int:
    app = AppContainer(root)
    app.initialize()
    try:
        security = _load_security(app, ticker)
        repository = FundamentalRepository(app.sqlite)
        providers = {
            "SEC_EDGAR": SECEdgarFundamentalsProvider(
                mirror_root=app.resolve_data_path("sec_mirror")
            ),
            "FINNHUB": FinnhubFundamentalsProvider(),
            "SIMFIN": SimFinFundamentalsProvider(os.getenv("SIMFIN_FUNDAMENTALS_PATH")),
            "FMP": FMPFundamentalsProvider(),
        }
        result = await FundamentalEngine(repository, providers, ProviderHealthRepository(app.sqlite)).sync_security(
            security,
            provider_mode=provider,
            include_estimates=True,
            include_metrics=True,
        )
        print(f"TICKER: {result.ticker}")
        print(f"PROVIDER MODE: {result.provider_mode}")
        print(f"PROVIDERS USED: {', '.join(result.providers_used)}")
        print(f"FILINGS LOADED: {result.filings_loaded}")
        print(f"FACTS LOADED: {result.facts_loaded}")
        print(f"ESTIMATES LOADED: {result.estimates_loaded}")
        print(f"KPIS/METRICS LOADED: {result.kpis_loaded}")
        print(f"VALIDATIONS: {result.validations_run}")
        return 0
    finally:
        app.close()


def show_fundamentals(root: Path, ticker: str, as_of_text: str) -> int:
    app = AppContainer(root)
    app.initialize()
    try:
        security = _load_security(app, ticker)
        as_of_date = date.fromisoformat(as_of_text)
        as_of = datetime.combine(as_of_date, time.max, tzinfo=timezone.utc)
        repository = FundamentalRepository(app.sqlite)
        snapshot = FundamentalSnapshotService(repository).snapshot_as_of(
            security.security_id, as_of
        )
        print(f"TICKER: {ticker.upper()}")
        print(f"AS OF: {as_of.isoformat()}")
        print("TTM:")
        print(json.dumps(snapshot.ttm, indent=2, sort_keys=True))
        print("LATEST CANONICAL FACTS:")
        compact = {
            metric: {
                "value": row["value"],
                "unit": row["unit"],
                "period_end": row["period_end"],
                "source": row["source"],
                "accepted_at": row["accepted_at"],
                "available_at": row["available_at"],
                "accession_number": row["accession_number"],
                "validation_status": row["validation_status"],
            }
            for metric, row in sorted(snapshot.facts.items())
        }
        print(json.dumps(compact, indent=2, sort_keys=True))
        return 0
    finally:
        app.close()


def show_validation(root: Path, ticker: str) -> int:
    app = AppContainer(root)
    app.initialize()
    try:
        security = _load_security(app, ticker)
        payload = ValidationRepository(app.sqlite).summary(security.security_id)
        print(json.dumps(
            {
                "ticker": security.ticker,
                "security_id": security.security_id,
                **payload,
            },
            indent=2,
            sort_keys=True,
            default=str,
        ))
        return 0
    finally:
        app.close()


def ingest_ir_json(root: Path, ticker: str, json_path: str) -> int:
    app = AppContainer(root)
    app.initialize()
    try:
        security = _load_security(app, ticker)
        payload = json.loads(Path(json_path).read_text(encoding="utf-8"))
        records = payload.get("records", []) if isinstance(payload, dict) else payload
        if not isinstance(records, list):
            raise ValueError("IR JSON must be a list or {'records': [...]} object")
        provider = CompanyInvestorRelationsProvider()
        rows = provider.ingest_structured(
            security,
            records,
            retrieved_at=datetime.now(timezone.utc),
        )
        count = FundamentalRepository(app.sqlite).save_guidance_kpis(rows)
        print(f"IR KPI/GUIDANCE RECORDS STORED: {count}")
        return 0
    finally:
        app.close()


def run_v12(root: Path, ticker: str, as_of_text: str) -> int:
    app = AppContainer(root)
    app.initialize()
    try:
        security = _load_security(app, ticker)
        as_of_date = date.fromisoformat(as_of_text)
        as_of = datetime.combine(as_of_date, time.max, tzinfo=timezone.utc)
        feature_repo = ModelFeatureRepository(app.sqlite)
        model_input = S153V12InputLoader(feature_repo).load(
            security_id=security.security_id,
            ticker=security.ticker,
            as_of=as_of,
        )
        result = S153V12Model().analyze(model_input)
        analysis_id = ModelRunRepository(app.sqlite).save_v12(
            model_input,
            result,
            config_path=root / "config" / "s153_v12.yaml",
        )
        payload = {
            "analysis_id": analysis_id,
            "ticker": result.ticker,
            "as_of": result.as_of.isoformat(),
            "score": result.score,
            "status": result.status,
            "verdict": result.verdict,
            "primary_route": result.primary_route,
            "secondary_route": result.secondary_route,
            "route_gate": result.route_gate,
            "confidence": result.confidence,
            "precision_confirmed": result.precision_confirmed,
            "strong_watch": result.strong_watch,
            "discovery": result.discovery,
            "missing_requirements": list(result.missing_requirements),
            "routes": dict(result.routes),
            "components": dict(result.components),
            "flags": dict(result.flags),
        }
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return 0
    finally:
        app.close()


def ingest_stooq_bulk(root: Path, zip_path: str) -> int:
    app = AppContainer(root)
    app.initialize()
    try:
        security_repo = SecurityRepository(app.sqlite)
        price_repo = PriceRepository(
            app.sqlite, ParquetPriceStore(app.resolve_data_path(app.app_config.database.parquet_root))
        )
        provider = StooqPriceProvider()
        count = 0
        series_count = 0
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
    parser.add_argument("--ui", action="store_true", help="Launch the desktop UI")
    parser.add_argument("--doctor", action="store_true", help="Validate architecture")

    parser.add_argument("--sync-universe", action="store_true", help="Sync US universe")
    parser.add_argument("--as-of", help="Universe PIT date YYYY-MM-DD; default=today")
    parser.add_argument("--no-delisted", action="store_true", help="Skip current delisted archive sync")
    parser.add_argument("--ticker-events", type=int, default=0, help="Fetch ticker-change events for first N securities")
    parser.add_argument("--sync-global-reference", action="store_true", help="Sync broad global ticker reference database")
    parser.add_argument("--global-market", help="Optional country/market code filter, e.g. US/JP/TR/HK")

    parser.add_argument("--sync-price", metavar="TICKER", help="Sync one ticker's historical daily prices")
    parser.add_argument("--price-start", help="Price start YYYY-MM-DD")
    parser.add_argument("--price-end", help="Price end YYYY-MM-DD")
    parser.add_argument("--price-provider", default="AUTO", help="AUTO/MASSIVE/STOOQ/SIMFIN/YAHOO_COMPAT/MARKETPARQUET")
    parser.add_argument("--ingest-stooq-bulk", metavar="ZIP", help="Bootstrap local Stooq bulk ZIP into Parquet")

    parser.add_argument("--sync-fundamentals", metavar="TICKER", help="Sync one ticker's filings/fundamentals")
    parser.add_argument("--fund-provider", default="AUTO", help="AUTO/SEC_EDGAR/FINNHUB/SIMFIN/FMP")
    parser.add_argument("--show-fundamentals", metavar="TICKER", help="Show canonical PIT fundamental snapshot")
    parser.add_argument("--fund-as-of", help="Fundamental snapshot date YYYY-MM-DD")
    parser.add_argument(
        "--show-validation",
        metavar="TICKER",
        help="Show persisted price/fundamental cross-provider validation diagnostics",
    )
    parser.add_argument("--ingest-ir-json", metavar="JSON", help="Ingest structured official IR KPI/guidance JSON")
    parser.add_argument("--ir-ticker", help="Ticker for --ingest-ir-json")

    parser.add_argument("--run-v12", metavar="TICKER", help="Run canonical S15.3 V1.2 from PIT canonical model features")
    parser.add_argument("--model-as-of", help="V1.2 analysis date YYYY-MM-DD")

    args = parser.parse_args()
    root = Path(__file__).resolve().parent

    if args.ui:
        from app.ui.launcher import launch_ui
        return launch_ui(root)
    if args.doctor:
        return doctor(root)
    if args.sync_universe:
        as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
        return asyncio.run(sync_universe(root, as_of, not args.no_delisted, args.ticker_events))
    if args.sync_global_reference:
        return asyncio.run(sync_global_reference(root, args.global_market))
    if args.sync_price:
        if not args.price_start or not args.price_end:
            parser.error("--sync-price requires --price-start and --price-end")
        return asyncio.run(sync_price(
            root,
            args.sync_price,
            date.fromisoformat(args.price_start),
            date.fromisoformat(args.price_end),
            args.price_provider,
        ))
    if args.ingest_stooq_bulk:
        return ingest_stooq_bulk(root, args.ingest_stooq_bulk)
    if args.sync_fundamentals:
        return asyncio.run(sync_fundamentals(root, args.sync_fundamentals, args.fund_provider))
    if args.show_fundamentals:
        if not args.fund_as_of:
            parser.error("--show-fundamentals requires --fund-as-of YYYY-MM-DD")
        return show_fundamentals(root, args.show_fundamentals, args.fund_as_of)
    if args.show_validation:
        return show_validation(root, args.show_validation)
    if args.ingest_ir_json:
        if not args.ir_ticker:
            parser.error("--ingest-ir-json requires --ir-ticker")
        return ingest_ir_json(root, args.ir_ticker, args.ingest_ir_json)
    if args.run_v12:
        if not args.model_as_of:
            parser.error("--run-v12 requires --model-as-of YYYY-MM-DD")
        return run_v12(root, args.run_v12, args.model_as_of)

    from app.ui.launcher import launch_ui
    return launch_ui(root)


if __name__ == "__main__":
    raise SystemExit(main())
