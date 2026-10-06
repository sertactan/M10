from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from core.contracts.enums import Exchange
from core.prices.engine import HistoricalPriceEngine
from core.prices.policy import auto_provider_priority
from core.universe.models import UniverseRecord
from core.universe.service import USUniverseService
from data.database.sqlite_store import SQLiteStore
from data.repositories.provider_health_repository import ProviderHealthRepository
from data.repositories.security_repository import SecurityRepository


class _Provider:
    def __init__(self, configured: bool = True) -> None:
        self.configured = configured


def test_free_price_route_requires_no_paid_provider() -> None:
    providers = {
        "MASSIVE": _Provider(False),
        "MARKETPARQUET": _Provider(False),
        "STOOQ": _Provider(True),
        "SIMFIN": _Provider(False),
        "YAHOO_COMPAT": _Provider(True),
    }
    assert auto_provider_priority(providers) == ("STOOQ", "YAHOO_COMPAT")


def test_configured_paid_provider_is_optional_accelerator_only() -> None:
    providers = {
        "MASSIVE": _Provider(True),
        "MARKETPARQUET": _Provider(True),
        "STOOQ": _Provider(True),
        "SIMFIN": _Provider(False),
        "YAHOO_COMPAT": _Provider(True),
    }
    assert auto_provider_priority(providers) == (
        "MASSIVE",
        "MARKETPARQUET",
        "STOOQ",
        "YAHOO_COMPAT",
    )


def test_health_router_never_promotes_fallback_yahoo_above_free_primary(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "ops.sqlite")
    store.initialize()
    try:
        health = ProviderHealthRepository(store, failure_threshold=5)
        providers = {
            "MASSIVE": _Provider(False),
            "MARKETPARQUET": _Provider(False),
            "STOOQ": _Provider(True),
            "SIMFIN": _Provider(False),
            "YAHOO_COMPAT": _Provider(True),
        }

        # Make Yahoo operationally healthier than Stooq. Phase 4 still keeps
        # FALLBACK_ONLY sources behind eligible historical sources.
        health.record_failure("STOOQ", latency_ms=3000.0, message="temporary outage")
        health.record_success("YAHOO_COMPAT", latency_ms=100.0)

        engine = HistoricalPriceEngine(None, providers, health)  # ordering test only
        assert engine._provider_order("AUTO") == ("STOOQ", "YAHOO_COMPAT")
        assert engine._provider_order("YAHOO_COMPAT") == ("YAHOO_COMPAT",)
    finally:
        store.close()


class _SEC:
    def __init__(self, records):
        self.records = records
        self.calls = 0

    async def list_current_us_securities(self):
        self.calls += 1
        return self.records


class _Massive:
    configured = True

    def __init__(self, delisted):
        self.delisted = delisted
        self.calls: list[tuple[object, object]] = []

    async def list_us_securities(self, as_of=None, active=True):
        self.calls.append((as_of, active))
        if active:
            raise AssertionError("current universe must not use Massive as active primary")
        return self.delisted

    async def ticker_events(self, identifier):
        return []


class _FinnhubOff:
    configured = False


@pytest.mark.asyncio
async def test_current_universe_is_sec_primary_even_when_massive_is_configured(tmp_path) -> None:
    now = datetime.now(timezone.utc)
    today = now.date()
    store = SQLiteStore(tmp_path / "ops.sqlite")
    store.initialize()
    try:
        sec_record = UniverseRecord(
            ticker="FREE",
            name="Free First Corp",
            exchange=Exchange.NASDAQ,
            exchange_mic="XNAS",
            active=True,
            provider="SEC_EDGAR",
            availability_date=now,
            security_type="CS",
            cik="0000001234",
        )
        delisted = UniverseRecord(
            ticker="OLD",
            name="Old Corp",
            exchange=Exchange.NYSE,
            exchange_mic="XNYS",
            active=False,
            provider="MASSIVE",
            availability_date=now,
            security_type="CS",
        )
        sec = _SEC([sec_record])
        massive = _Massive([delisted])
        service = USUniverseService(
            SecurityRepository(store),
            sec=sec,
            massive=massive,
            finnhub=_FinnhubOff(),
        )

        result = await service.sync(as_of=today, include_delisted=True)

        assert result.source_mode == "SEC_CURRENT_PRIMARY"
        assert result.active_loaded == 1
        assert result.delisted_loaded == 1
        assert sec.calls == 1
        assert massive.calls == [(None, False)]
    finally:
        store.close()


class _MassiveOff:
    configured = False


@pytest.mark.asyncio
async def test_historical_pit_still_fails_closed_without_optional_massive(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "ops.sqlite")
    store.initialize()
    try:
        service = USUniverseService(
            SecurityRepository(store),
            sec=_SEC([]),
            massive=_MassiveOff(),
            finnhub=_FinnhubOff(),
        )
        historical = datetime.now(timezone.utc).date() - timedelta(days=30)
        with pytest.raises(RuntimeError, match="Historical US universe sync requires MASSIVE_API_KEY"):
            await service.sync(as_of=historical)
    finally:
        store.close()
