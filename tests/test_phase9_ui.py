from __future__ import annotations

import os
from datetime import date, datetime, timezone
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from app.ui.analysis_service import DesktopAnalysisView
from app.ui.main_window import ResearchTerminalWindow
from app.ui.price_chart import PricePointView
from app.ui.theme import APP_QSS
from app.ui.view_models import BacktestView, ForecastView, ModelView, StockHeaderView
from core.backtest.contracts import ForwardOutcome
from core.backtest.outcomes import CanonicalForwardOutcomeEngine
from core.prices.models import AdjustmentStatus, PriceQualityStatus, SourcePriceBar
from core.forecast.contracts import CalibratedForecast, ForecastResult
from data.database.sqlite_store import SQLiteStore
from data.repositories.backtest_repository import BacktestRepository
from data.repositories.price_repository import PriceRepository
from data.repositories.forecast_calibration_repository import ForecastCalibrationRepository
from data.repositories.forecast_run_repository import ForecastRunRepository
from data.storage.parquet_price_store import ParquetPriceStore


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_phase9_shell_has_required_global_header_and_tabs(qapp):
    window = ResearchTerminalWindow()
    try:
        assert window.windowTitle() == "S15.3 Research Terminal"
        assert window.market.count() == 1
        assert window.market.currentText() == "United States"
        assert window.horizon.currentData() == 12
        assert window.tabs.count() == 3
        assert [window.tabs.tabText(i) for i in range(3)] == [
            "V1.2", "V1.4", "COMPARE"
        ]
        assert window.v12_page.score.text() == "—"
        assert window.v12_page.status.text() == "NOT LOADED"
        assert window.v14_page.score.text() == "—"
        assert window.v14_page.status.text() == "NOT LOADED"
        assert window.stock_header.price.text() == "—"
        assert window.context_panel.backtest_status.text() == "NOT AVAILABLE"
        assert window.context_panel.forecast_status.text() == "NOT AVAILABLE"
        assert "background: #0B1220" in APP_QSS
    finally:
        window.close()


def test_phase9_empty_ticker_does_not_dispatch_analysis(qapp):
    window = ResearchTerminalWindow()
    emitted = []
    window.analysis_requested.connect(lambda ticker, as_of: emitted.append((ticker, as_of)))
    try:
        window.ticker.setText("")
        window.run_button.click()
        assert emitted == []
        assert window.status.text() == "Ticker is required"
    finally:
        window.close()


def test_phase9_normalizes_ticker_and_emits_request(qapp):
    window = ResearchTerminalWindow()
    emitted = []
    window.analysis_requested.connect(lambda ticker, as_of: emitted.append((ticker, as_of)))
    try:
        window.ticker.setText("crmd")
        window.run_button.click()
        assert emitted
        assert emitted[0][0] == "CRMD"
        assert window.status.text() == "Analysis backend is not connected"
    finally:
        window.close()


def test_phase9_applies_real_result_surface_without_synthetic_consensus(qapp):
    window = ResearchTerminalWindow()
    result = DesktopAnalysisView(
        ticker="TEST",
        as_of=datetime(2026, 10, 6, tzinfo=timezone.utc),
        stock=StockHeaderView(
            ticker="TEST",
            name="Test Inc.",
            exchange="NASDAQ",
            status="CANONICAL PRICE",
            price=11.0,
            change_pct=10.0,
            price_date="2026-10-06",
            price_source="BACKTEST · TEST",
        ),
        backtest=BacktestView(
            status="READY",
            entry_price=10.0,
            fm252=3.2,
            max_multiple_observed=3.2,
            outcome_class="STRONG_WINNER",
            anchor_session="2026-10-06",
            horizon_sessions_available=252,
        ),
        forecast=ForecastView(status="NOT AVAILABLE"),
        price_points=[
            PricePointView(trade_date=date(2026, 10, 5), adjusted_close=10.0),
            PricePointView(trade_date=date(2026, 10, 6), adjusted_close=11.0),
        ],
        v12=ModelView(
            model_name="S15.3 V1.2",
            status="READY",
            score=81.2,
            route="F10",
            destination=None,
            confidence=78.0,
            risk=None,
        ),
        v14=ModelView(
            model_name="S15.3 V1.4",
            status="BLOCKED_CANONICAL_SPEC",
        ),
        v12_components={"Core15.3": 81.2},
        v14_components={},
    )
    try:
        window._apply_analysis(result)
        assert window.stock_header.ticker.text() == "TEST"
        assert window.stock_header.price.text() == "$11.00"
        assert window.stock_header.change.text() == "+10.00%"
        assert window.context_panel.backtest_status.text() == "READY"
        assert window.context_panel.backtest_values["FM252"].text() == "3.20x"
        assert window.context_panel.forecast_status.text() == "NOT AVAILABLE"
        assert len(window.v12_page.price_chart.chart.series()) == 2
        assert len(window.v14_page.price_chart.chart.series()) == 2
        assert window.v12_page.score.text() == "81.2 / 100"
        assert window.v12_page.route.text() == "F10"
        assert window.v14_page.status.text() == "BLOCKED_CANONICAL_SPEC"
        assert window.compare_page.consensus.text() == "MODEL CONSENSUS: —"
        assert window.compare_page.winner.text() == "Winner: —"
        assert "LOADED TEST" in window.status.text()
    finally:
        window.close()



def test_phase9_canonical_price_and_backtest_connections(tmp_path):
    store = SQLiteStore(tmp_path / "ui.sqlite")
    store.initialize()
    try:
        now = datetime(2026, 10, 6, tzinfo=timezone.utc)
        store.connection.execute(
            """
            INSERT INTO security_master (
                security_id,ticker,name,exchange,market,active,created_at,updated_at
            ) VALUES (?,?,?,?,?,?,?,?)
            """,
            ("SEC_TEST","TEST","Test Inc.","NASDAQ","US",1,now.isoformat(),now.isoformat()),
        )
        store.connection.commit()

        parquet = ParquetPriceStore(tmp_path / "parquet")
        price_repo = PriceRepository(store, parquet)
        bars = [
            SourcePriceBar(
                security_id="SEC_TEST", source="TEST", source_symbol="TEST",
                trade_date=date(2026, 10, 5), open=10.0, high=10.5, low=9.5,
                raw_close=10.0, adjusted_close=10.0, volume=1000.0,
                retrieved_at=now, quality_status=PriceQualityStatus.PRIMARY,
                adjustment_status=AdjustmentStatus.DUAL_RAW_ADJUSTED,
            ),
            SourcePriceBar(
                security_id="SEC_TEST", source="TEST", source_symbol="TEST",
                trade_date=date(2026, 10, 6), open=10.5, high=11.5, low=10.0,
                raw_close=11.0, adjusted_close=11.0, volume=1200.0,
                retrieved_at=now, quality_status=PriceQualityStatus.PRIMARY,
                adjustment_status=AdjustmentStatus.DUAL_RAW_ADJUSTED,
            ),
        ]
        price_repo.save_series(bars)
        price_repo.select_series(
            security_id="SEC_TEST",
            start=date(2026, 10, 5),
            end=date(2026, 10, 6),
            source="TEST",
            source_symbol="TEST",
            purpose="BACKTEST",
            reason="phase9-test",
        )

        outcome = ForwardOutcome(
            security_id="SEC_TEST",
            as_of_date_requested=date(2026, 10, 6),
            anchor_session=date(2026, 10, 6),
            anchor_lag_calendar_days=0,
            entry_adjusted_close=11.0,
            horizon_sessions_available=252,
            fm252=3.2,
            max_multiple_observed=3.2,
            outcome_class="STRONG_WINNER",
            outcome_status="READY",
        )
        BacktestRepository(store, parquet).save_forward_outcome(outcome)

        fake_app = SimpleNamespace(
            sqlite=store,
            app_config=SimpleNamespace(
                database=SimpleNamespace(parquet_root="parquet")
            ),
        )
        row = store.connection.execute(
            "SELECT security_id,ticker,name,exchange FROM security_master WHERE security_id='SEC_TEST'"
        ).fetchone()

        from app.ui.analysis_service import DesktopAnalysisService
        service = DesktopAnalysisService(tmp_path)
        stock = service._load_stock(fake_app, row, date(2026, 10, 6))
        backtest = service._load_backtest(fake_app, "SEC_TEST", date(2026, 10, 6))
        price_points = service._load_price_points(fake_app, "SEC_TEST", date(2026, 10, 6))

        assert stock.status == "CANONICAL PRICE"
        assert stock.price == 11.0
        assert stock.change_pct == pytest.approx(10.0)
        assert stock.price_date == "2026-10-06"
        assert len(price_points) == 2
        assert price_points[-1].adjusted_close == 11.0
        assert backtest.status == "READY"
        assert backtest.fm252 == 3.2
        assert backtest.outcome_class == "STRONG_WINNER"
    finally:
        store.close()



def test_phase9_loads_persisted_validated_forecast(tmp_path):
    store = SQLiteStore(tmp_path / "forecast-ui.sqlite")
    store.initialize()
    try:
        now = datetime(2026, 10, 6, 9, 0, tzinfo=timezone.utc)
        store.connection.execute(
            """
            INSERT INTO security_master (
                security_id,ticker,name,exchange,market,active,created_at,updated_at
            ) VALUES (?,?,?,?,?,?,?,?)
            """,
            ("SEC_TEST","TEST","Test Inc.","NASDAQ","US",1,now.isoformat(),now.isoformat()),
        )
        store.connection.execute(
            """
            INSERT INTO backtest_run_manifest (
                run_id,created_at,s15_spec_version,backtest_spec_version,
                random_seed,status
            ) VALUES (?,?,?,?,?,?)
            """,
            ("RUN-UI",now.isoformat(),"S15.3_TEST","PHASE6_TEST",0,"COMPLETE"),
        )
        store.connection.commit()

        calibration = CalibratedForecast(
            calibration_id="CAL-UI",
            calibration_source="PHASE6_MARKET_PREVALENCE_WALK_FORWARD",
            calibration_cutoff=datetime(2026, 10, 5, tzinfo=timezone.utc),
            sample_size=1000,
            bull_return_pct=120.0,
            base_return_pct=45.0,
            bear_return_pct=-30.0,
            probability_positive_return_pct=70.0,
            probability_2x_plus_pct=25.0,
            probability_5x_plus_pct=7.0,
            probability_10x_plus_pct=2.0,
            confidence_pct=80.0,
            risk="MEDIUM",
            metadata={},
        )
        calibration_repo = ForecastCalibrationRepository(store)
        evidence_hash = calibration_repo.save_validated_profile(
            run_id="RUN-UI",
            model_version="S15.3_TEST",
            horizon_months=12,
            dataset_kind="MARKET_PREVALENCE",
            calibration_method="UNBIASED_WALK_FORWARD",
            calibration=calibration,
            evidence={
                "walk_forward_pass": True,
                "leakage_audit_pass": True,
                "survivorship_audit_pass": True,
                "future_outcome_in_feature_matrix": False,
            },
        )
        result = ForecastResult(
            security_id="SEC_TEST",
            ticker="TEST",
            as_of=now,
            horizon_months=12,
            v12_score=80.0,
            v12_status="READY",
            v12_route="F10",
            v12_destination=None,
            v14_score=85.0,
            v14_status="READY",
            v14_route="EARLY_ASYMMETRIC",
            v14_destination="3X-5X",
            bull_return_pct=120.0,
            base_return_pct=45.0,
            bear_return_pct=-30.0,
            probability_positive_return_pct=70.0,
            probability_2x_plus_pct=25.0,
            probability_5x_plus_pct=7.0,
            probability_10x_plus_pct=2.0,
            confidence_pct=80.0,
            risk="MEDIUM",
            calibration_id="CAL-UI",
            calibration_source="PHASE6_MARKET_PREVALENCE_WALK_FORWARD",
            calibration_cutoff=datetime(2026, 10, 5, tzinfo=timezone.utc),
            calibration_sample_size=1000,
            calibration_metadata={"evidence_hash": evidence_hash},
        )
        receipt = ForecastRunRepository(store).save(
            result=result,
            v12_model_version="S15.3_V1.2",
            v14_model_version="S15.3_V1.4",
            data_snapshot_hash="a" * 64,
            model_config_hash="b" * 64,
        )

        fake_app = SimpleNamespace(sqlite=store)
        from app.ui.analysis_service import DesktopAnalysisService
        view = DesktopAnalysisService(tmp_path)._load_forecast(
            fake_app, "SEC_TEST", date(2026, 10, 6)
        )
        assert view.status == "VALIDATED FORECAST"
        assert view.analysis_id == receipt.analysis_id
        assert view.base_return_pct == 45.0
        assert view.probability_10x_plus_pct == 2.0
        assert view.calibration_id == "CAL-UI"
    finally:
        store.close()
