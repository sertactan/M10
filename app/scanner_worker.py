from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from collections.abc import Callable
from typing import Any


class ScannerWorker:
    """Run a scan off the UI thread.

    The factory pattern intentionally allows each worker thread to construct its
    own repositories/database connection instead of sharing a UI-thread SQLite
    connection across threads.
    """

    def __init__(self, scanner_factory: Callable[[], Any]) -> None:
        self.scanner_factory = scanner_factory
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="s153-scan")

    def submit(self, method_name: str, **kwargs) -> Future:
        def run():
            scanner = self.scanner_factory()
            method = getattr(scanner, method_name)
            return method(**kwargs)

        return self._executor.submit(run)

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
