from __future__ import annotations

from collections import OrderedDict
from collections.abc import Hashable
from dataclasses import dataclass
from threading import RLock
from typing import Generic, TypeVar


K = TypeVar("K", bound=Hashable)
V = TypeVar("V")


@dataclass(frozen=True)
class CacheStats:
    hits: int
    misses: int
    evictions: int
    size: int
    capacity: int


class BoundedLRUCache(Generic[K, V]):
    """Small thread-safe LRU cache.

    Callers are responsible for including a provenance/version token in the key
    whenever cached data can change. This prevents cache freshness policy from
    silently altering canonical/PIT semantics.
    """

    def __init__(self, capacity: int = 16) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >=1")
        self.capacity = capacity
        self._items: OrderedDict[K, V] = OrderedDict()
        self._lock = RLock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def get(self, key: K) -> V | None:
        with self._lock:
            if key not in self._items:
                self._misses += 1
                return None
            value = self._items.pop(key)
            self._items[key] = value
            self._hits += 1
            return value

    def put(self, key: K, value: V) -> None:
        with self._lock:
            if key in self._items:
                self._items.pop(key)
            self._items[key] = value
            if len(self._items) > self.capacity:
                self._items.popitem(last=False)
                self._evictions += 1

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    @property
    def stats(self) -> CacheStats:
        with self._lock:
            return CacheStats(
                hits=self._hits,
                misses=self._misses,
                evictions=self._evictions,
                size=len(self._items),
                capacity=self.capacity,
            )
