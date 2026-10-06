from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable, Generic, Iterable, TypeVar


T = TypeVar("T")


@dataclass(frozen=True)
class ProviderRaceResult(Generic[T]):
    provider: str
    value: T | None
    error: Exception | None


async def race_in_canonical_order(
    providers: Iterable[str],
    probe: Callable[[str], Awaitable[T]],
    accept: Callable[[ProviderRaceResult[T]], bool],
) -> ProviderRaceResult[T] | None:
    """Run provider probes concurrently while preserving canonical order.

    Lower-priority providers may finish early, but they are never accepted until
    every provider ahead of them has completed and failed eligibility. When a
    winner is accepted, all remaining losing requests are cancelled.
    """

    order = tuple(providers)
    if not order:
        return None

    tasks = {
        asyncio.create_task(probe(name)): index
        for index, name in enumerate(order)
    }
    buffered: dict[int, ProviderRaceResult[T]] = {}
    next_index = 0

    try:
        while tasks:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                index = tasks.pop(task)
                name = order[index]
                try:
                    value = task.result()
                    buffered[index] = ProviderRaceResult(name, value, None)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    buffered[index] = ProviderRaceResult(name, None, exc)

            while next_index in buffered:
                result = buffered.pop(next_index)
                if accept(result):
                    for pending in tasks:
                        pending.cancel()
                    if tasks:
                        await asyncio.gather(*tasks.keys(), return_exceptions=True)
                    return result
                next_index += 1

        while next_index in buffered:
            result = buffered.pop(next_index)
            if accept(result):
                return result
            next_index += 1
        return None
    finally:
        for pending in tasks:
            if not pending.done():
                pending.cancel()
        if tasks:
            await asyncio.gather(*tasks.keys(), return_exceptions=True)
