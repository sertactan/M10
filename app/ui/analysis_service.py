from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from pathlib import Path

from app.bootstrap import AppContainer
from app.ui.view_models import BacktestView, ForecastView, ModelView, StockHeaderView
from core.features.s153_v12_input_loader import S153V12InputLoader
from core.features.s153_v14_input_loader import S153V14InputLoader
from core.models.s153_v12 import S153V12Model
from core.models.s153_v14 import S153V14Model, V14CanonicalSpecificationMissing
from data.repositories.forecast_run_repository import ForecastReproducibilityError, ForecastRunRepository
from data.repositories.model_feature_repository import ModelFeatureRepository
from data.storage.parquet_price_store import ParquetPriceStore


@dataclass(frozen=True)
class DesktopAnalysisView:
    ticker: str
    as_of: datetime
    stock: StockHeaderView
    backtest: BacktestView
    forecast: ForecastView
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

    def _load_stock(self, app: AppContainer, row, as_of_date: date) -> StockHeaderView:
        selection = app.sqlite.connection.execute(
            """
            SELECT *
            FROM canonical_price_selection
            WHERE security_id=?
              AND start_date<=?
              AND end_date>=?
            ORDER BY selected_at DESC
            LIMIT 1
            """,
            (row['security_id'], as_of_date.isoformat(), as_of_date.isoformat()),
        ).fetchone()
        if selection is None:
            return StockHeaderView(
                ticker=row['ticker'],
                name=row['name'],
                exchange=row['exchange'],
                status='PRICE NOT AVAILABLE',
            )

        parquet = ParquetPriceStore(self.root / app.app_config.database.parquet_root)
        start = date.fromisoformat(selection['start_date'])
        end = min(as_of_date, date.fromisoformat(selection['end_date']))
        frame = parquet.read_bars(
            security_id=row['security_id'],
            source=selection['source'],
            source_symbol=selection['source_symbol'],
            start_date=start,
            end_date=end,
        )
        if frame.empty:
            return StockHeaderView(
                ticker=row['ticker'],
                name=row['name'],
                exchange=row['exchange'],
                status='PRICE SERIES NOT AVAILABLE',
                price_source=f"{selection['purpose']} · {selection['source']}",
            )

        ordered = frame.sort_values('trade_date')
        latest = ordered.iloc[-1]
        price = float(latest['adjusted_close'])
        change_pct = None
        if len(ordered) >= 2:
            previous = float(ordered.iloc[-2]['adjusted_close'])
            if previous != 0:
                change_pct = (price / previous - 1.0) * 100.0
        price_date = str(latest['trade_date'])[:10]
        return StockHeaderView(
            ticker=row['ticker'],
            name=row['name'],
            exchange=row['exchange'],
            status='CANONICAL PRICE',
            price=price,
            change_pct=change_pct,
            price_date=price_date,
            price_source=f"{selection['purpose']} · {selection['source']}",
        )

    @staticmethod
    def _load_backtest(app: AppContainer, security_id: str, as_of_date: date) -> BacktestView:
        row = app.sqlite.connection.execute(
            """
            SELECT *
            FROM forward_outcomes
            WHERE security_id=? AND as_of_date_requested=?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (security_id, as_of_date.isoformat()),
        ).fetchone()
        if row is None:
            return BacktestView(status='NOT AVAILABLE')
        return BacktestView(
            status=row['outcome_status'],
            entry_price=row['entry_adjusted_close'],
            fm252=row['fm252'],
            max_multiple_observed=row['max_multiple_observed'],
            outcome_class=row['outcome_class'],
            anchor_session=row['anchor_session'],
            horizon_sessions_available=row['horizon_sessions_available'],
            time_to_2x_sessions=row['time_to_2x_sessions'],
            time_to_5x_sessions=row['time_to_5x_sessions'],
            time_to_10x_sessions=row['time_to_10x_sessions'],
        )

    @staticmethod
    def _load_forecast(app: AppContainer, security_id: str, as_of_date: date) -> ForecastView:
        row = app.sqlite.connection.execute(
            """
            SELECT analysis_id
            FROM forecast_runs
            WHERE security_id=? AND analysis_date LIKE ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (security_id, as_of_date.isoformat() + '%'),
        ).fetchone()
        if row is None:
            return ForecastView(status='NOT AVAILABLE')
        try:
            stored = ForecastRunRepository(app.sqlite).load(row['analysis_id'])
        except ForecastReproducibilityError:
            return ForecastView(status='INVALID STORED FORECAST')
        payload = stored['forecast_payload']
        return ForecastView(
            status='VALIDATED FORECAST',
            bull_return_pct=payload.get('bull_return_pct'),
            base_return_pct=payload.get('base_return_pct'),
            bear_return_pct=payload.get('bear_return_pct'),
            probability_positive_return_pct=payload.get('probability_positive_return_pct'),
            probability_2x_plus_pct=payload.get('probability_2x_plus_pct'),
            probability_5x_plus_pct=payload.get('probability_5x_plus_pct'),
            probability_10x_plus_pct=payload.get('probability_10x_plus_pct'),
            confidence_pct=payload.get('confidence_pct'),
            risk=payload.get('risk'),
            calibration_id=payload.get('calibration_id'),
            analysis_id=row['analysis_id'],
        )

    def analyze(self, *, ticker: str, as_of_date: date) -> DesktopAnalysisView:
        app = AppContainer(self.root)
        app.initialize()
        try:
            row = app.sqlite.connection.execute(
                """
                SELECT security_id,ticker,name,exchange
                FROM security_master
                WHERE ticker=?
                ORDER BY active DESC, updated_at DESC
                LIMIT 1
                """,
                (ticker.upper(),),
            ).fetchone()
            if row is None:
                raise RuntimeError(
                    f'Ticker not found in canonical security_master: {ticker.upper()}'
                )

            as_of = datetime.combine(as_of_date, time.max, tzinfo=timezone.utc)
            stock = self._load_stock(app, row, as_of_date)
            backtest = self._load_backtest(app, row['security_id'], as_of_date)
            forecast = self._load_forecast(app, row['security_id'], as_of_date)
            features = ModelFeatureRepository(app.sqlite)

            v12_input = S153V12InputLoader(features).load(
                security_id=row['security_id'],
                ticker=row['ticker'],
                as_of=as_of,
            )
            v12_result = S153V12Model().analyze(v12_input)
            v12_view = ModelView(
                model_name='S15.3 V1.2',
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
                    security_id=row['security_id'],
                    ticker=row['ticker'],
                    as_of=as_of,
                )
                v14_result = S153V14Model().analyze(v14_input)
                v14_view = ModelView(
                    model_name='S15.3 V1.4',
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
                    model_name='S15.3 V1.4',
                    status='BLOCKED_CANONICAL_SPEC',
                )

            return DesktopAnalysisView(
                ticker=row['ticker'],
                as_of=as_of,
                stock=stock,
                backtest=backtest,
                forecast=forecast,
                v12=v12_view,
                v14=v14_view,
                v12_components=dict(v12_result.components),
                v14_components=v14_components,
            )
        finally:
            app.close()
