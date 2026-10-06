from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import date, datetime, time, timedelta, timezone
import os
from pathlib import Path

from app.bootstrap import AppContainer
from app.bulk_data_bootstrap import (
    ensure_sec_companyfacts_bulk,
    ensure_stooq_scanner_bulk,
)
from app.data_bootstrap import ensure_current_universe_sync
from app.feature_materializer import CanonicalFeatureMaterializer
from core.optimization.parallel_scanner import ParallelMarketScanner
from core.scanner.production import RepositoryCandidateSource
from core.universe.service import USUniverseService
from app.ui.parallel_scoring import WorkerLocalCanonicalScorer
from data.providers.finnhub_universe import FinnhubUniverseProvider
from data.providers.massive_universe import MassiveUniverseProvider
from data.providers.sec_edgar_universe import SECEdgarUniverseProvider
from data.repositories.security_repository import SecurityRepository


class DesktopScannerService:
    def __init__(self, root: Path) -> None:
        self.root = root

    @staticmethod
    def _materialize_cached(app: AppContainer, as_of_date: date) -> int:
        as_of = datetime.combine(as_of_date, time.max, tzinfo=timezone.utc)
        price_cutoff = (
            as_of_date - timedelta(days=7)
            if as_of_date == date.today()
            else as_of_date
        )
        rows = app.sqlite.connection.execute(
            """
            SELECT DISTINCT s.*
            FROM security_master s
            WHERE s.market='US'
              AND s.exchange IN ('NASDAQ','NYSE','AMEX')
              AND EXISTS (
                  SELECT 1 FROM canonical_price_selection p
                  WHERE p.security_id=s.security_id
                    AND p.start_date<=?
                    AND p.end_date>=?
              )
              AND EXISTS (
                  SELECT 1 FROM fundamental_facts_source f
                  WHERE f.security_id=s.security_id
                    AND f.available_at<=?
              )
            ORDER BY s.ticker
            """,
            (
                as_of_date.isoformat(),
                price_cutoff.isoformat(),
                as_of.isoformat(),
            ),
        ).fetchall()
        materializer = CanonicalFeatureMaterializer(app)
        completed = 0
        for row in rows:
            materializer.materialize(row, as_of_date=as_of_date)
            completed += 1
        return completed

    @staticmethod
    def _ensure_historical_snapshot(app: AppContainer, as_of_date: date) -> None:
        repository = SecurityRepository(app.sqlite)
        if repository.universe_as_of(as_of_date):
            return
        massive = MassiveUniverseProvider()
        if not massive.configured:
            raise RuntimeError(
                "Historical PIT universe is not installed for this date. "
                "Set MASSIVE_API_KEY (the app will sync it automatically) "
                "or import a PIT-capable historical universe dataset. "
                "Current-universe substitution is forbidden."
            )
        service = USUniverseService(
            repository,
            sec=SECEdgarUniverseProvider(
                mirror_root=app.resolve_data_path("sec_mirror")
            ),
            massive=massive,
            finnhub=FinnhubUniverseProvider(),
        )
        asyncio.run(
            service.sync(
                as_of=as_of_date,
                include_delisted=True,
                ticker_event_limit=0,
            )
        )

    def scan(self, *, as_of_date: date):
        app = AppContainer(self.root)
        app.initialize()
        try:
            notes: list[str] = []
            if as_of_date == date.today():
                ensure_current_universe_sync(app)
                try:
                    sec_count, sec_facts = ensure_sec_companyfacts_bulk(app)
                    if sec_facts:
                        notes.append(
                            f"SEC bulk prepared {sec_count} securities / {sec_facts} facts"
                        )
                except Exception as exc:
                    notes.append(f"SEC bulk unavailable: {exc}")
                try:
                    stooq_series, stooq_bars = ensure_stooq_scanner_bulk(app)
                    if stooq_bars:
                        notes.append(
                            f"Stooq scanner cache prepared {stooq_series} series / {stooq_bars} bars"
                        )
                except Exception as exc:
                    notes.append(f"Stooq bulk unavailable: {exc}")
            else:
                self._ensure_historical_snapshot(app, as_of_date)

            materialized = self._materialize_cached(app, as_of_date)
            if materialized:
                notes.append(f"canonical features materialized for {materialized} securities")

            as_of = datetime.combine(as_of_date, time.max, tzinfo=timezone.utc)
            candidates = RepositoryCandidateSource(SecurityRepository(app.sqlite))
            workers = max(1, min(4, os.cpu_count() or 1))
            scanner = ParallelMarketScanner(
                candidates,
                scorer_factory=lambda: WorkerLocalCanonicalScorer(self.root),
                workers=workers,
                batch_size=500,
            )
            if as_of_date == date.today():
                rows, summary = scanner.scan_current(as_of=as_of)
            else:
                rows, summary = scanner.scan_historical(as_of=as_of)
            return rows, replace(summary, notes=tuple(notes))
        finally:
            app.close()
