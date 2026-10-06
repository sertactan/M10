from __future__ import annotations

from datetime import date, datetime, time, timezone
from pathlib import Path

from app.bootstrap import AppContainer
from core.scanner.engine import MarketScanner
from core.scanner.production import CanonicalDualModelScorer, RepositoryCandidateSource
from data.repositories.model_feature_repository import ModelFeatureRepository
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
            scorer = CanonicalDualModelScorer(ModelFeatureRepository(app.sqlite))
            scanner = MarketScanner(candidates, scorer, batch_size=500)
            if as_of_date == date.today():
                return scanner.scan_current(as_of=as_of)
            return scanner.scan_historical(as_of=as_of)
        finally:
            app.close()
