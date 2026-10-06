from __future__ import annotations

import asyncio
import logging
import queue
import threading
from datetime import date
from pathlib import Path

from app.bootstrap import AppContainer
from app.data_bootstrap import (
    ensure_current_universe,
    ensure_price_history,
    ensure_sec_fundamentals,
)
from core.data_sync.service import BackgroundDataSyncService
from data.repositories.background_sync_repository import BackgroundSyncRepository

log = logging.getLogger(__name__)


class BackgroundSyncRuntime:
    """Persistent, non-blocking desktop data refresh loop.

    The worker owns its AppContainer and SQLite connection. The UI thread only
    submits ticker warm-up requests through a thread-safe queue.
    """

    def __init__(
        self,
        root: Path,
        *,
        warm_ticker: str | None = None,
        poll_seconds: float = 15.0,
        concurrency: int = 2,
    ) -> None:
        self.root = root
        self.warm_ticker = (warm_ticker or "").strip().upper() or None
        self.poll_seconds = max(1.0, float(poll_seconds))
        self.concurrency = max(1, int(concurrency))
        self._stop = threading.Event()
        self._ticker_requests: queue.SimpleQueue[str] = queue.SimpleQueue()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="m10-background-data-sync",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)

    def request_ticker_warmup(self, ticker: str) -> None:
        value = ticker.strip().upper()
        if value:
            self._ticker_requests.put(value)

    @staticmethod
    def _load_row(app: AppContainer, ticker: str):
        return app.sqlite.connection.execute(
            """
            SELECT *
            FROM security_master
            WHERE ticker=?
            ORDER BY active DESC, updated_at DESC
            LIMIT 1
            """,
            (ticker.upper(),),
        ).fetchone()

    def _schedule_daily_tasks(
        self,
        repo: BackgroundSyncRepository,
        *,
        ticker: str | None,
    ) -> None:
        today = date.today().isoformat()
        repo.enqueue(
            "UNIVERSE",
            f"universe:{today}",
            {"as_of": today},
            priority=10,
            max_attempts=4,
        )
        if ticker:
            repo.enqueue(
                "PRICE",
                f"price:{ticker}:{today}",
                {"ticker": ticker, "as_of": today},
                priority=20,
                max_attempts=4,
            )
            repo.enqueue(
                "FUNDAMENTALS",
                f"fundamentals:{ticker}:{today}",
                {"ticker": ticker, "as_of": today},
                priority=30,
                max_attempts=4,
            )

    def _run(self) -> None:
        app = AppContainer(self.root)
        try:
            app.initialize()
            repo = BackgroundSyncRepository(app.sqlite)

            async def universe_handler(payload: dict) -> None:
                await ensure_current_universe(app, force_refresh=True)

            async def price_handler(payload: dict) -> None:
                ticker = str(payload["ticker"]).upper()
                row = self._load_row(app, ticker)
                if row is None:
                    await ensure_current_universe(app, force_refresh=True)
                    row = self._load_row(app, ticker)
                if row is None:
                    raise RuntimeError(f"ticker not found after universe refresh: {ticker}")
                await ensure_price_history(
                    app,
                    row,
                    as_of_date=date.fromisoformat(str(payload["as_of"])),
                    force_refresh=True,
                    incremental=True,
                )

            async def fundamentals_handler(payload: dict) -> None:
                ticker = str(payload["ticker"]).upper()
                row = self._load_row(app, ticker)
                if row is None:
                    raise RuntimeError(f"ticker not found for fundamentals refresh: {ticker}")
                await ensure_sec_fundamentals(
                    app,
                    row,
                    as_of_date=date.fromisoformat(str(payload["as_of"])),
                    force_refresh=True,
                )

            service = BackgroundDataSyncService(
                repo,
                {
                    "UNIVERSE": universe_handler,
                    "PRICE": price_handler,
                    "FUNDAMENTALS": fundamentals_handler,
                },
                concurrency=self.concurrency,
                batch_size=8,
                retry_base_seconds=5,
                retry_cap_seconds=300,
            )

            active_ticker = self.warm_ticker
            while not self._stop.is_set():
                while True:
                    try:
                        active_ticker = self._ticker_requests.get_nowait()
                    except queue.Empty:
                        break

                self._schedule_daily_tasks(repo, ticker=active_ticker)
                summary = asyncio.run(service.run_ready_batch())
                if summary.claimed:
                    log.info(
                        "Background sync batch claimed=%s succeeded=%s retried=%s failed=%s",
                        summary.claimed,
                        summary.succeeded,
                        summary.retried,
                        summary.failed,
                    )
                self._stop.wait(self.poll_seconds)
        except Exception:
            log.exception("Background data sync runtime stopped after an unexpected error")
        finally:
            app.close()
