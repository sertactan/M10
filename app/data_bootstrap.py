from __future__ import annotations

import asyncio
import os
from datetime import date, datetime, time, timedelta, timezone
from time import perf_counter

from app.bootstrap import AppContainer
from core.contracts.entities import Security
from core.contracts.enums import Exchange
from data.providers.sec_edgar_fundamentals import SECEdgarFundamentalsProvider
from data.providers.sec_edgar_universe import SECEdgarUniverseProvider
from data.providers.stooq_price import StooqPriceProvider
from data.providers.yahoo_price import YahooCompatiblePriceProvider
from data.repositories.fundamental_repository import FundamentalRepository
from data.repositories.model_feature_repository import ModelFeatureRepository
from data.repositories.price_repository import PriceRepository
from data.repositories.provider_health_repository import ProviderHealthRepository
from data.repositories.security_repository import SecurityRepository
from data.storage.parquet_price_store import ParquetPriceStore


DEFAULT_SEC_USER_AGENT = (
    "S15.3 Research Terminal "
    "(https://github.com/sertactan/M10)"
)


def _sec_user_agent() -> str:
    return os.getenv("SEC_USER_AGENT") or DEFAULT_SEC_USER_AGENT


def _security_from_row(row) -> Security:
    return Security(
        security_id=str(row["security_id"]),
        ticker=str(row["ticker"]),
        name=str(row["name"]),
        exchange=Exchange(str(row["exchange"])),
        cik=str(row["cik"]) if row["cik"] else None,
        sector=row["sector"],
        industry=row["industry"],
        ipo_date=date.fromisoformat(row["ipo_date"]) if row["ipo_date"] else None,
        delisted_date=(
            date.fromisoformat(row["delisted_date"]) if row["delisted_date"] else None
        ),
        active=bool(row["active"]),
    )


async def ensure_current_universe(app: AppContainer, *, force_refresh: bool = False) -> int:
    repo = SecurityRepository(app.sqlite)
    existing = repo.current_us_common_stocks()
    if len(existing) >= 1000 and not force_refresh:
        return len(existing)

    health = ProviderHealthRepository(app.sqlite)
    if not health.can_attempt("SEC_EDGAR"):
        if existing and not force_refresh:
            return len(existing)
        raise RuntimeError("SEC_EDGAR circuit is open; background universe refresh deferred")

    provider = SECEdgarUniverseProvider(
        user_agent=_sec_user_agent(),
        mirror_root=app.resolve_data_path("sec_mirror"),
    )
    started = perf_counter()
    try:
        records = await provider.list_current_us_securities()
        if not records:
            if existing and not force_refresh:
                return len(existing)
            raise RuntimeError("SEC EDGAR returned an empty US universe")
        health.record_success(
            "SEC_EDGAR",
            latency_ms=(perf_counter() - started) * 1000.0,
        )
    except Exception as exc:
        text = str(exc)
        health.record_failure(
            "SEC_EDGAR",
            latency_ms=(perf_counter() - started) * 1000.0,
            rate_limited=("429" in text or "rate limit" in text.lower()),
            message=text[:500],
        )
        if existing and not force_refresh:
            return len(existing)
        raise

    repo.bulk_upsert(records, snapshot_date=date.today())
    return len(repo.current_us_common_stocks())


def ensure_current_universe_sync(app: AppContainer) -> int:
    return asyncio.run(ensure_current_universe(app))


async def ensure_price_history(
    app: AppContainer,
    row,
    *,
    as_of_date: date,
    lookback_days: int = 1095,
    force_refresh: bool = False,
    incremental: bool = False,
) -> int:
    existing = app.sqlite.connection.execute(
        """
        SELECT 1
        FROM canonical_price_selection
        WHERE security_id=?
          AND start_date<=?
          AND end_date>=?
        LIMIT 1
        """,
        (
            row["security_id"],
            as_of_date.isoformat(),
            as_of_date.isoformat(),
        ),
    ).fetchone()
    if existing is not None and not force_refresh:
        return 0

    last_known_good = app.sqlite.connection.execute(
        """
        SELECT 1
        FROM canonical_price_selection
        WHERE security_id=?
          AND start_date<=?
          AND end_date<?
        ORDER BY end_date DESC, selected_at DESC
        LIMIT 1
        """,
        (
            row["security_id"],
            as_of_date.isoformat(),
            as_of_date.isoformat(),
        ),
    ).fetchone()

    security = _security_from_row(row)
    health = ProviderHealthRepository(app.sqlite)
    start = as_of_date - timedelta(days=lookback_days)

    # Desktop live bootstrap is resilient to a Yahoo 429. Yahoo remains the
    # preferred adjusted UI source when healthy; Stooq is a real-data fallback
    # and is stored with its original BOOTSTRAP / RAW_ONLY provenance.
    providers = (
        ("YAHOO_COMPAT", YahooCompatiblePriceProvider()),
        ("STOOQ", StooqPriceProvider()),
    )
    errors: list[str] = []
    bars = None
    provider_name = None

    for name, provider in providers:
        if not health.can_attempt(name):
            errors.append(f"{name}: circuit open")
            continue

        provider_start = start
        if incremental:
            latest = app.sqlite.connection.execute(
                """
                SELECT end_date
                FROM price_series_registry
                WHERE security_id=? AND source=?
                ORDER BY end_date DESC
                LIMIT 1
                """,
                (security.security_id, name),
            ).fetchone()
            if latest is not None:
                overlap_start = date.fromisoformat(latest["end_date"]) - timedelta(days=7)
                provider_start = max(provider_start, overlap_start)

        started = perf_counter()
        try:
            candidate_bars = await provider.get_history(
                security, provider_start, as_of_date
            )
            if not candidate_bars:
                raise RuntimeError(f"No live price history returned for {security.ticker}")
            health.record_success(
                name,
                latency_ms=(perf_counter() - started) * 1000.0,
            )
            bars = candidate_bars
            provider_name = name
            break
        except Exception as exc:
            text = str(exc)
            health.record_failure(
                name,
                latency_ms=(perf_counter() - started) * 1000.0,
                rate_limited=("429" in text or "rate limit" in text.lower()),
                message=text[:500],
            )
            errors.append(f"{name}: {text}")

    if bars is None or provider_name is None:
        if last_known_good is not None and not force_refresh:
            return 0
        raise RuntimeError(
            f"No live price provider available for {security.ticker}: "
            + "; ".join(errors)
        )

    parquet = ParquetPriceStore(
        app.resolve_data_path(app.app_config.database.parquet_root)
    )
    repo = PriceRepository(app.sqlite, parquet)
    descriptor = repo.save_series(bars)

    purpose = (
        "UI_LIVE_FALLBACK"
        if provider_name == "YAHOO_COMPAT"
        else "UI_LIVE_BOOTSTRAP"
    )
    repo.select_series(
        security_id=security.security_id,
        start=descriptor.start_date,
        end=as_of_date,
        source=descriptor.source,
        source_symbol=descriptor.source_symbol,
        purpose=purpose,
        reason=(
            "real single-provider Yahoo adjusted-price fallback for desktop display"
            if provider_name == "YAHOO_COMPAT"
            else "real single-provider Stooq raw-price bootstrap after live-provider fallback"
        ),
    )

    last_bar = max(
        (bar for bar in bars if bar.trade_date <= as_of_date),
        key=lambda b: b.trade_date,
    )
    feature_as_of = datetime.combine(as_of_date, time.max, tzinfo=timezone.utc)
    ModelFeatureRepository(app.sqlite).save_feature(
        security_id=security.security_id,
        feature_key="RAW_CURRENT_PRICE",
        value=float(last_bar.adjusted_close),
        feature_as_of=feature_as_of,
        available_at=min(last_bar.retrieved_at, feature_as_of),
        source_phase="PHASE2_PRICE",
        source_ref=f"{provider_name}:{last_bar.source_symbol}:{last_bar.trade_date.isoformat()}",
        quality_status=last_bar.quality_status.value,
        computation_version="desktop-live-bootstrap-v2",
        evidence={
            "provider": provider_name,
            "trade_date": last_bar.trade_date.isoformat(),
            "adjustment_status": last_bar.adjustment_status.value,
        },
    )
    return len(bars)

def ensure_price_history_sync(app: AppContainer, row, *, as_of_date: date) -> int:
    return asyncio.run(ensure_price_history(app, row, as_of_date=as_of_date))


async def ensure_sec_fundamentals(
    app: AppContainer,
    row,
    *,
    as_of_date: date,
    force_refresh: bool = False,
) -> int:
    security = _security_from_row(row)
    if not security.cik:
        return 0

    cutoff = datetime.combine(as_of_date, time.max, tzinfo=timezone.utc)
    existing = app.sqlite.connection.execute(
        """
        SELECT COUNT(*) AS n
        FROM fundamental_facts_source
        WHERE security_id=? AND source='SEC_EDGAR' AND available_at<=?
        """,
        (security.security_id, cutoff.isoformat()),
    ).fetchone()
    if existing is not None and int(existing["n"]) > 0 and not force_refresh:
        return int(existing["n"])

    health = ProviderHealthRepository(app.sqlite)
    if not health.can_attempt("SEC_EDGAR"):
        if force_refresh:
            raise RuntimeError("SEC_EDGAR circuit is open; fundamentals refresh deferred")
        return 0

    provider = SECEdgarFundamentalsProvider(
        user_agent=_sec_user_agent(),
        mirror_root=app.resolve_data_path("sec_mirror"),
    )
    repo = FundamentalRepository(app.sqlite)
    started = perf_counter()
    try:
        filings = await provider.get_filings(security)
        facts = await provider.get_facts(security)
        repo.save_filings(filings)
        repo.save_facts(facts)
        health.record_success(
            "SEC_EDGAR",
            latency_ms=(perf_counter() - started) * 1000.0,
        )
        return len(facts)
    except Exception as exc:
        text = str(exc)
        health.record_failure(
            "SEC_EDGAR",
            latency_ms=(perf_counter() - started) * 1000.0,
            rate_limited=("429" in text or "rate limit" in text.lower()),
            message=text[:500],
        )
        raise


def ensure_sec_fundamentals_sync(app: AppContainer, row, *, as_of_date: date) -> int:
    return asyncio.run(ensure_sec_fundamentals(app, row, as_of_date=as_of_date))
