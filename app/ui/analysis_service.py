from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from app.bootstrap import AppContainer
from app.data_bootstrap import (
    ensure_current_universe_sync,
    ensure_price_history_sync,
    ensure_sec_fundamentals_sync,
)
from app.feature_materializer import CanonicalFeatureMaterializer
from app.ui.price_chart import PricePointView
from app.ui.view_models import BacktestView, ForecastView, ModelView, StockHeaderView
from core.backtest.outcomes import CanonicalForwardOutcomeEngine
from core.features.s153_v12_input_loader import S153V12InputLoader
from core.features.s153_v14_input_loader import S153V14InputLoader
from core.models.s153_v12 import S153V12Model
from core.models.s153_v141 import S153V141Model
from core.forecast.calibration import ForecastCalibrationUnavailable
from core.forecast.wf7_validated_provider import WF7ValidatedMagnitudeCalibrationProvider
from core.prices.models import AdjustmentStatus, PriceQualityStatus, SourcePriceBar
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
    price_points: list[PricePointView]
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

    @staticmethod
    def _select_price_window(app: AppContainer, security_id: str, as_of_date: date):
        exact = app.sqlite.connection.execute(
            """
            SELECT *
            FROM canonical_price_selection
            WHERE security_id=?
              AND start_date<=?
              AND end_date>=?
            ORDER BY selected_at DESC
            LIMIT 1
            """,
            (security_id, as_of_date.isoformat(), as_of_date.isoformat()),
        ).fetchone()
        if exact is not None:
            return exact, False

        cached = app.sqlite.connection.execute(
            """
            SELECT *
            FROM canonical_price_selection
            WHERE security_id=?
              AND start_date<=?
              AND end_date<?
            ORDER BY end_date DESC, selected_at DESC
            LIMIT 1
            """,
            (security_id, as_of_date.isoformat(), as_of_date.isoformat()),
        ).fetchone()
        return cached, cached is not None

    def _load_stock(self, app: AppContainer, row, as_of_date: date) -> StockHeaderView:
        selection, stale = self._select_price_window(
            app,
            row['security_id'],
            as_of_date,
        )
        if selection is None:
            return StockHeaderView(
                ticker=row['ticker'],
                name=row['name'],
                exchange=row['exchange'],
                status='PRICE NOT AVAILABLE',
            )

        parquet = ParquetPriceStore(app.resolve_data_path(app.app_config.database.parquet_root))
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
            status='CACHED STALE PRICE' if stale else 'CANONICAL PRICE',
            price=price,
            change_pct=change_pct,
            price_date=price_date,
            price_source=(
                f"LKG · {selection['purpose']} · {selection['source']}"
                if stale
                else f"{selection['purpose']} · {selection['source']}"
            ),
        )

    def _load_price_points(self, app: AppContainer, security_id: str, as_of_date: date) -> list[PricePointView]:
        selection, _stale = self._select_price_window(app, security_id, as_of_date)
        if selection is None:
            return []
        parquet = ParquetPriceStore(app.resolve_data_path(app.app_config.database.parquet_root))
        start = date.fromisoformat(selection['start_date'])
        end = min(as_of_date, date.fromisoformat(selection['end_date']))
        frame = parquet.read_bars(
            security_id=security_id,
            source=selection['source'],
            source_symbol=selection['source_symbol'],
            start_date=start,
            end_date=end,
        )
        if frame.empty:
            return []
        points: list[PricePointView] = []
        for item in frame.sort_values('trade_date').to_dict(orient='records'):
            trade_date = item['trade_date']
            if not isinstance(trade_date, date):
                trade_date = date.fromisoformat(str(trade_date)[:10])
            points.append(
                PricePointView(
                    trade_date=trade_date,
                    adjusted_close=float(item['adjusted_close']),
                )
            )
        return points

    @staticmethod
    def _backtest_view_from_outcome(outcome) -> BacktestView:
        return BacktestView(
            status=outcome.outcome_status,
            entry_price=outcome.entry_adjusted_close,
            fm252=outcome.fm252,
            max_multiple_observed=outcome.max_multiple_observed,
            outcome_class=outcome.outcome_class,
            anchor_session=(
                outcome.anchor_session.isoformat()
                if outcome.anchor_session is not None
                else None
            ),
            horizon_sessions_available=outcome.horizon_sessions_available,
            time_to_2x_sessions=outcome.time_to_2x_sessions,
            time_to_5x_sessions=outcome.time_to_5x_sessions,
            time_to_10x_sessions=outcome.time_to_10x_sessions,
        )

    @classmethod
    def _load_backtest(cls, app: AppContainer, security_id: str, as_of_date: date) -> BacktestView:
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
        if row is not None:
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

        # For an individual historical analysis, a PIT market-universe snapshot is
        # not required to calculate the canonical forward-price label. Reuse one
        # already-selected adjusted single-provider series, but never use RAW_ONLY
        # Stooq data as if it were an adjusted-close target series.
        selection = app.sqlite.connection.execute(
            """
            SELECT p.*, r.adjustment_status, r.quality_status, r.retrieved_at
            FROM canonical_price_selection p
            JOIN price_series_registry r
              ON r.security_id=p.security_id
             AND r.source=p.source
             AND r.source_symbol=p.source_symbol
            WHERE p.security_id=?
              AND p.start_date<=?
              AND p.end_date>?
            ORDER BY p.end_date DESC, p.selected_at DESC
            LIMIT 1
            """,
            (security_id, as_of_date.isoformat(), as_of_date.isoformat()),
        ).fetchone()
        if selection is None:
            return BacktestView(status='NOT AVAILABLE')

        adjustment = AdjustmentStatus(str(selection['adjustment_status']))
        if adjustment in {AdjustmentStatus.RAW_ONLY, AdjustmentStatus.UNKNOWN}:
            return BacktestView(status='ADJUSTED FORWARD SERIES NOT AVAILABLE')

        parquet = ParquetPriceStore(
            app.resolve_data_path(app.app_config.database.parquet_root)
        )
        start = date.fromisoformat(selection['start_date'])
        end = date.fromisoformat(selection['end_date'])
        frame = parquet.read_bars(
            security_id=security_id,
            source=selection['source'],
            source_symbol=selection['source_symbol'],
            start_date=start,
            end_date=end,
        )
        if frame.empty:
            return BacktestView(status='NOT AVAILABLE')

        bars: list[SourcePriceBar] = []
        for item in frame.sort_values('trade_date').to_dict(orient='records'):
            trade_date = item['trade_date']
            if not isinstance(trade_date, date):
                trade_date = date.fromisoformat(str(trade_date)[:10])
            retrieved_at = item['retrieved_at']
            if not isinstance(retrieved_at, datetime):
                retrieved_at = datetime.fromisoformat(str(retrieved_at).replace('Z', '+00:00'))
            if retrieved_at.tzinfo is None:
                retrieved_at = retrieved_at.replace(tzinfo=timezone.utc)
            bars.append(
                SourcePriceBar(
                    security_id=security_id,
                    source=str(item['source']),
                    source_symbol=str(item['source_symbol']),
                    trade_date=trade_date,
                    open=float(item['open']),
                    high=float(item['high']),
                    low=float(item['low']),
                    raw_close=float(item['raw_close']),
                    adjusted_close=float(item['adjusted_close']),
                    volume=float(item['volume']),
                    vwap=(None if item.get('vwap') is None else float(item['vwap'])),
                    retrieved_at=retrieved_at,
                    quality_status=PriceQualityStatus(str(item['quality_status'])),
                    adjustment_status=AdjustmentStatus(str(item['adjustment_status'])),
                    raw_payload_hash=item.get('raw_payload_hash'),
                )
            )
        outcome = CanonicalForwardOutcomeEngine().compute(
            security_id=security_id,
            as_of_date_requested=as_of_date,
            bars=bars,
        )
        return cls._backtest_view_from_outcome(outcome)

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
                SELECT *
                FROM security_master
                WHERE ticker=?
                ORDER BY active DESC, updated_at DESC
                LIMIT 1
                """,
                (ticker.upper(),),
            ).fetchone()

            if row is None and as_of_date == date.today():
                ensure_current_universe_sync(app)
                row = app.sqlite.connection.execute(
                    """
                    SELECT *
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

            price_fetch_date = as_of_date
            price_lookback_days = 1095
            if as_of_date < date.today():
                price_fetch_date = date.today()
                price_lookback_days = max(
                    1095,
                    (price_fetch_date - as_of_date).days + 500,
                )
            ensure_price_history_sync(
                app,
                row,
                as_of_date=price_fetch_date,
                lookback_days=price_lookback_days,
            )
            try:
                ensure_sec_fundamentals_sync(app, row, as_of_date=as_of_date)
            except Exception:
                # Price/UI data remains usable even if SEC is temporarily unavailable.
                pass

            # Bridge Phase 1-3 canonical data into the model feature layer.
            # Only deterministic/evidenced factors are written; unavailable
            # qualitative/analyst/catalyst inputs remain N/A.
            CanonicalFeatureMaterializer(app).materialize(
                row,
                as_of_date=as_of_date,
            )

            as_of = datetime.combine(as_of_date, time.max, tzinfo=timezone.utc)
            stock = self._load_stock(app, row, as_of_date)
            backtest = self._load_backtest(app, row['security_id'], as_of_date)
            forecast = self._load_forecast(app, row['security_id'], as_of_date)
            price_points = self._load_price_points(app, row['security_id'], as_of_date)
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

            v14_input = S153V14InputLoader(features).load(
                security_id=row['security_id'],
                ticker=row['ticker'],
                as_of=as_of,
            )
            v14_result = S153V141Model().analyze(v14_input)
            v14_view = ModelView(
                model_name='S15.3 V1.4.1',
                status=v14_result.status,
                score=v14_result.score,
                route=v14_result.primary_route,
                destination=v14_result.primary_magnitude,
                confidence=v14_result.confidence,
                risk=None,
            )
            v14_components: dict[str, object] = dict(v14_result.components)

            if (
                forecast.status == 'NOT AVAILABLE'
                and as_of_date == date.today()
                and v14_result.score is not None
            ):
                try:
                    calibrated = WF7ValidatedMagnitudeCalibrationProvider(
                        app.sqlite,
                    ).calibrate(
                        score=v14_result.score,
                        as_of=as_of,
                    )
                    forecast = ForecastView(
                        status='WF7 VALIDATED OOS MAGNITUDE',
                        bull_return_pct=None,
                        base_return_pct=None,
                        bear_return_pct=None,
                        probability_positive_return_pct=None,
                        probability_2x_plus_pct=calibrated.probability_2x_plus_pct,
                        probability_5x_plus_pct=calibrated.probability_5x_plus_pct,
                        probability_10x_plus_pct=calibrated.probability_10x_plus_pct,
                        confidence_pct=v14_result.confidence,
                        risk=(
                            f'WF7_OOS_BUCKET {calibrated.bucket_label} · '
                            f'N={calibrated.sample_size} · {calibrated.sample_quality}'
                        ),
                        calibration_id=calibrated.calibration_id,
                    )
                except ForecastCalibrationUnavailable as exc:
                    forecast = ForecastView(
                        status=f'WF7 CALIBRATION NOT AVAILABLE — {exc}'
                    )

            return DesktopAnalysisView(
                ticker=row['ticker'],
                as_of=as_of,
                stock=stock,
                backtest=backtest,
                forecast=forecast,
                price_points=price_points,
                v12=v12_view,
                v14=v14_view,
                v12_components={
                    **dict(v12_result.components),
                    "MISSING_REQUIREMENTS": (
                        ", ".join(v12_result.missing_requirements)
                        if v12_result.missing_requirements
                        else "—"
                    ),
                },
                v14_components=v14_components,
            )
        finally:
            app.close()
