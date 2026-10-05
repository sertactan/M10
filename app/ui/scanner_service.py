from __future__ import annotations

from datetime import date, datetime, time, timezone
import os
from pathlib import Path

from app.bootstrap import AppContainer
from core.optimization.parallel_scanner import ParallelMarketScanner
from core.scanner.production import RepositoryCandidateSource
from app.ui.parallel_scoring import WorkerLocalCanonicalScorer
from data.repositories.security_repository import SecurityRepository


class DesktopScannerService:
    def __init__(self, root: Path) -> None:
        self.root = root

    def scan(self, *, as_of_date: date):
        app = AppContainer(self.root)
        app.initialize()
        try:
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
                return scanner.scan_current(as_of=as_of)
            return scanner.scan_historical(as_of=as_of)
        finally:
            app.close()
