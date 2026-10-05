from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from pathlib import Path

from app.bootstrap import AppContainer
from app.ui.view_models import ModelView
from core.features.s153_v12_input_loader import S153V12InputLoader
from core.features.s153_v14_input_loader import S153V14InputLoader
from core.models.s153_v12 import S153V12Model
from core.models.s153_v14 import S153V14Model, V14CanonicalSpecificationMissing
from data.repositories.model_feature_repository import ModelFeatureRepository


@dataclass(frozen=True)
class DesktopAnalysisView:
    ticker: str
    as_of: datetime
    v12: ModelView
    v14: ModelView
    v12_components: dict[str, object]
    v14_components: dict[str, object]


class DesktopAnalysisService:
    """Read canonical local state and run model engines for the desktop UI.

    A fresh AppContainer/database connection is created per analysis task so UI
    and worker threads do not share a SQLite connection.
    """

    def __init__(self, root: Path) -> None:
        self.root = root

    def analyze(self, *, ticker: str, as_of_date: date) -> DesktopAnalysisView:
        app = AppContainer(self.root)
        app.initialize()
        try:
            row = app.sqlite.connection.execute(
                """
                SELECT security_id,ticker
                FROM security_master
                WHERE ticker=?
                ORDER BY active DESC, updated_at DESC
                LIMIT 1
                """,
                (ticker.upper(),),
            ).fetchone()
            if row is None:
                raise RuntimeError(
                    f"Ticker not found in canonical security_master: {ticker.upper()}"
                )

            as_of = datetime.combine(as_of_date, time.max, tzinfo=timezone.utc)
            features = ModelFeatureRepository(app.sqlite)

            v12_input = S153V12InputLoader(features).load(
                security_id=row["security_id"],
                ticker=row["ticker"],
                as_of=as_of,
            )
            v12_result = S153V12Model().analyze(v12_input)
            v12_view = ModelView(
                model_name="S15.3 V1.2",
                status=v12_result.status,
                score=v12_result.score,
                route=v12_result.primary_route,
                destination=None,
                confidence=v12_result.confidence,
                risk=None,
            )

            v14_components: dict[str, object] = {}
            try:
                v14_input = S153V14InputLoader(features).load(
                    security_id=row["security_id"],
                    ticker=row["ticker"],
                    as_of=as_of,
                )
                v14_result = S153V14Model().analyze(v14_input)
                v14_view = ModelView(
                    model_name="S15.3 V1.4",
                    status=v14_result.status,
                    score=v14_result.score,
                    route=v14_result.primary_route,
                    destination=v14_result.primary_magnitude,
                    confidence=v14_result.confidence,
                    risk=None,
                )
                v14_components = dict(v14_result.components)
            except V14CanonicalSpecificationMissing:
                v14_view = ModelView(
                    model_name="S15.3 V1.4",
                    status="BLOCKED_CANONICAL_SPEC",
                )

            return DesktopAnalysisView(
                ticker=row["ticker"],
                as_of=as_of,
                v12=v12_view,
                v14=v14_view,
                v12_components=dict(v12_result.components),
                v14_components=v14_components,
            )
        finally:
            app.close()
