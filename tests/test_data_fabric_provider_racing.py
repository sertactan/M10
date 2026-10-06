from __future__ import annotations

import asyncio

import pytest

from core.data_sync.racing import race_in_canonical_order


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
