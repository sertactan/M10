from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from core.contracts.entities import Security
from core.contracts.enums import Exchange
from core.fundamentals.engine import FundamentalEngine


SECURITY = Security(
    security_id="SEC_TEST",
    ticker="TEST",
    name="Test Corp",
    exchange=Exchange.NASDAQ,
)


class _Connection:
    def execute(self, *args, **kwargs):
        return self

    def commit(self):
        return None


class _Repository:
    def __init__(self):
        self.store = SimpleNamespace(connection=_Connection())

    def save_filings(self, rows):
        return len(list(rows))

    def save_facts(self, rows):
        return len(list(rows))

    def save_estimates(self, rows):
        return len(list(rows))

    def save_guidance_kpis(self, rows):
        return len(list(rows))

    def validate_against_sec(self, security_id):
        return 0


class _Provider:
    configured = True

    def __init__(
        self,
        name,
        *,
        sec_done=None,
        active=None,
        delay=0.01,
    ):
        self.name = name
        self.sec_done = sec_done
        self.active = active
        self.delay = delay

    async def validate_symbol(self, security):
        if self.name != "SEC_EDGAR" and self.sec_done is not None:
            assert self.sec_done.is_set()
        return True

    async def get_filings(self, security):
        if self.active is not None:
            self.active["now"] += 1
            self.active["max"] = max(self.active["max"], self.active["now"])
            await asyncio.sleep(self.delay)
            self.active["now"] -= 1
        else:
            await asyncio.sleep(self.delay)
        return []

    async def get_facts(self, security):
        await asyncio.sleep(0)
        if self.name == "SEC_EDGAR" and self.sec_done is not None:
            self.sec_done.set()
        return []

    async def get_estimates(self, security):
        return []

    async def get_company_metrics(self, security):
        return []


@pytest.mark.asyncio
async def test_sec_finishes_before_secondary_enrichment_starts():
    sec_done = asyncio.Event()
    active = {"now": 0, "max": 0}
    providers = {
        "SEC_EDGAR": _Provider("SEC_EDGAR", sec_done=sec_done),
        "FINNHUB": _Provider("FINNHUB", sec_done=sec_done, active=active),
        "SIMFIN": _Provider("SIMFIN", sec_done=sec_done, active=active),
        "FMP": _Provider("FMP", sec_done=sec_done, active=active),
    }
    engine = FundamentalEngine(_Repository(), providers)

    result = await engine.sync_security(SECURITY)

    assert result.providers_used == ("SEC_EDGAR", "FINNHUB", "SIMFIN", "FMP")
    assert active["max"] >= 2


@pytest.mark.asyncio
async def test_per_provider_concurrency_limit_is_enforced():
    active = {"now": 0, "max": 0}
    provider = _Provider("FINNHUB", active=active, delay=0.02)
    engine = FundamentalEngine(
        _Repository(),
        {"FINNHUB": provider},
        provider_concurrency_limits={"FINNHUB": 1},
    )

    await asyncio.gather(
        engine._sync_one_provider(
            "FINNHUB",
            SECURITY,
            include_estimates=False,
            include_metrics=False,
        ),
        engine._sync_one_provider(
            "FINNHUB",
            SECURITY,
            include_estimates=False,
            include_metrics=False,
        ),
    )

    assert active["max"] == 1
