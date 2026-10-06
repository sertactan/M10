from __future__ import annotations

import asyncio

import pytest

from core.data_sync.service import BackgroundDataSyncService
from data.database.sqlite_store import SQLiteStore
from data.repositories.background_sync_repository import BackgroundSyncRepository


@pytest.mark.asyncio
async def test_background_sync_retries_then_succeeds(tmp_path):
    store = SQLiteStore(tmp_path / "ops.sqlite")
    store.initialize()
    try:
        repo = BackgroundSyncRepository(store)
        calls = 0

        async def flaky(payload):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("temporary upstream outage")

        repo.enqueue(
            "PRICE",
            "price:TEST:2026-10-06",
            {"ticker": "TEST"},
            max_attempts=3,
        )
        service = BackgroundDataSyncService(
            repo,
            {"PRICE": flaky},
            concurrency=2,
            retry_base_seconds=0,
            retry_cap_seconds=0,
        )

        first = await service.run_ready_batch()
        assert first.claimed == 1
        assert first.retried == 1
        assert repo.counts()["RETRY"] == 1

        second = await service.run_ready_batch()
        assert second.succeeded == 1
        assert repo.counts()["SUCCEEDED"] == 1
        assert calls == 2
    finally:
        store.close()


@pytest.mark.asyncio
async def test_background_sync_enforces_bounded_concurrency(tmp_path):
    store = SQLiteStore(tmp_path / "ops.sqlite")
    store.initialize()
    try:
        repo = BackgroundSyncRepository(store)
        active = 0
        max_active = 0

        async def handler(payload):
            nonlocal active, max_active
            active += 1
            max_active = max(max_active, active)
            await asyncio.sleep(0.02)
            active -= 1

        for index in range(6):
            repo.enqueue(
                "PRICE",
                f"price:TEST{index}:2026-10-06",
                {"ticker": f"TEST{index}"},
            )

        service = BackgroundDataSyncService(
            repo,
            {"PRICE": handler},
            concurrency=2,
            batch_size=8,
        )
        result = await service.run_ready_batch()

        assert result.claimed == 6
        assert result.succeeded == 6
        assert max_active == 2
    finally:
        store.close()


def test_background_sync_deduplicates_daily_work(tmp_path):
    store = SQLiteStore(tmp_path / "ops.sqlite")
    store.initialize()
    try:
        repo = BackgroundSyncRepository(store)
        first = repo.enqueue("UNIVERSE", "universe:2026-10-06", {"as_of": "2026-10-06"})
        second = repo.enqueue("UNIVERSE", "universe:2026-10-06", {"as_of": "2026-10-06"})
        assert first == second
        assert sum(repo.counts().values()) == 1
    finally:
        store.close()
