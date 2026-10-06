from __future__ import annotations

import asyncio

import pytest

from core.contracts.entities import Security
from core.contracts.enums import Exchange
from core.data_sync.racing import race_in_canonical_order
from core.prices.engine import HistoricalPriceEngine


@pytest.mark.asyncio
async def test_race_preserves_canonical_priority_even_if_lower_finishes_first():
    finished = []

    async def probe(name):
        if name == "PRIMARY":
            await asyncio.sleep(0.03)
        else:
            await asyncio.sleep(0.005)
        finished.append(name)
        return name

    result = await race_in_canonical_order(
        ("PRIMARY", "SECONDARY"),
        probe,
        lambda item: item.error is None,
    )

    assert "SECONDARY" in finished
    assert result is not None
    assert result.provider == "PRIMARY"


@pytest.mark.asyncio
async def test_race_uses_already_finished_fallback_after_primary_failure():
    async def probe(name):
        if name == "PRIMARY":
            await asyncio.sleep(0.03)
            raise RuntimeError("primary down")
        await asyncio.sleep(0.005)
        return "fallback-data"

    result = await race_in_canonical_order(
        ("PRIMARY", "SECONDARY"),
        probe,
        lambda item: item.error is None,
    )

    assert result is not None
    assert result.provider == "SECONDARY"
    assert result.value == "fallback-data"


@pytest.mark.asyncio
async def test_race_cancels_losing_requests_after_valid_winner():
    cancelled = asyncio.Event()

    async def probe(name):
        if name == "PRIMARY":
            await asyncio.sleep(0.005)
            return "winner"
        try:
            await asyncio.sleep(10)
            return "loser"
        except asyncio.CancelledError:
            cancelled.set()
            raise

    result = await race_in_canonical_order(
        ("PRIMARY", "SECONDARY"),
        probe,
        lambda item: item.error is None,
    )

    assert result is not None
    assert result.provider == "PRIMARY"
    assert cancelled.is_set()


@pytest.mark.asyncio
async def test_price_provider_concurrency_limit_is_enforced():
    active = {"now": 0, "max": 0}

    class Provider:
        configured = True

        async def validate_symbol(self, security):
            return True

        async def get_history(self, security, start, end):
            active["now"] += 1
            active["max"] = max(active["max"], active["now"])
            await asyncio.sleep(0.02)
            active["now"] -= 1
            return ["bar"]

    security = Security(
        security_id="SEC_TEST",
        ticker="TEST",
        name="Test Corp",
        exchange=Exchange.NASDAQ,
    )
    engine = HistoricalPriceEngine(
        None,
        {"SIMFIN": Provider()},
        provider_concurrency_limits={"SIMFIN": 1},
    )

    await asyncio.gather(
        engine._probe_history_provider("SIMFIN", security, None, None),
        engine._probe_history_provider("SIMFIN", security, None, None),
    )

    assert active["max"] == 1
