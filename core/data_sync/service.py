from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable

from data.repositories.background_sync_repository import (
    BackgroundSyncRepository,
    BackgroundSyncTask,
)

SyncHandler = Callable[[dict], Awaitable[object]]


@dataclass(frozen=True)
class SyncBatchSummary:
    claimed: int = 0
    succeeded: int = 0
    retried: int = 0
    failed: int = 0


class BackgroundDataSyncService:
    def __init__(
        self,
        repository: BackgroundSyncRepository,
        handlers: dict[str, SyncHandler],
        *,
        concurrency: int = 2,
        batch_size: int = 8,
        retry_base_seconds: int = 5,
        retry_cap_seconds: int = 300,
    ) -> None:
        if concurrency < 1:
            raise ValueError("concurrency must be >= 1")
        if batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        self.repository = repository
        self.handlers = handlers
        self.concurrency = int(concurrency)
        self.batch_size = int(batch_size)
        self.retry_base_seconds = max(0, int(retry_base_seconds))
        self.retry_cap_seconds = max(self.retry_base_seconds, int(retry_cap_seconds))

    def _retry_delay(self, task: BackgroundSyncTask) -> int:
        exponent = max(0, task.attempts - 1)
        return min(self.retry_cap_seconds, self.retry_base_seconds * (2**exponent))

    async def _execute(
        self,
        task: BackgroundSyncTask,
        semaphore: asyncio.Semaphore,
    ) -> str:
        async with semaphore:
            handler = self.handlers.get(task.task_type)
            if handler is None:
                return self.repository.mark_failure(
                    task,
                    f"no handler registered for task type {task.task_type}",
                    retry_delay_seconds=0,
                )
            try:
                await handler(task.payload)
            except Exception as exc:
                return self.repository.mark_failure(
                    task,
                    str(exc),
                    retry_delay_seconds=self._retry_delay(task),
                )
            self.repository.mark_success(task.task_id)
            return "SUCCEEDED"

    async def run_ready_batch(self) -> SyncBatchSummary:
        tasks = self.repository.claim_ready(limit=self.batch_size)
        if not tasks:
            return SyncBatchSummary()

        semaphore = asyncio.Semaphore(self.concurrency)
        outcomes = await asyncio.gather(*(self._execute(task, semaphore) for task in tasks))
        return SyncBatchSummary(
            claimed=len(tasks),
            succeeded=sum(1 for status in outcomes if status == "SUCCEEDED"),
            retried=sum(1 for status in outcomes if status == "RETRY"),
            failed=sum(1 for status in outcomes if status == "FAILED"),
        )
