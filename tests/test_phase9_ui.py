from __future__ import annotations

import os
from datetime import date, datetime, timezone
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from app.ui.acceptance import PHASE9_ACCEPTANCE_ITEMS, UIAcceptanceItem, require_phase9_complete
from app.ui.analysis_service import DesktopAnalysisView
from app.ui.main_window import ResearchTerminalWindow
from app.ui.price_chart import PricePointView
from app.ui.scanner_dialog import MarketScannerDialog
from app.ui.theme import APP_QSS
from app.ui.view_models import BacktestView, ForecastView, ModelView, StockHeaderView
from core.backtest.contracts import ForwardOutcome
from core.backtest.outcomes import CanonicalForwardOutcomeEngine
from core.prices.models import AdjustmentStatus, PriceQualityStatus, SourcePriceBar
from core.scanner.contracts import ScanMode, ScanRow, ScanSummary
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
        assert window.minimumWidth() == 1100
        assert not window.progress.isVisible()
        assert "background: #0B1220" in APP_QSS
    finally:
        window.close()


def test_phase9_model_page_shows_partial_dna_when_final_score_missing(qapp):
    window = ResearchTerminalWindow()
    try:
        view = ModelView(
            model_name="S15.3 V1.2",
            status="INCONCLUSIVE",
            score=None,
            route="D10",
        )
        window.v12_page.set_model(
            view,
            {
                "DNA60": 63.4,
                "S15.2": None,
                "MISSING_REQUIREMENTS": "S15.2, M10>=5/7",
            },
        )
        assert window.v12_page.score.text() == "DNA60 63.4 · PARTIAL"
        assert window.v12_page.status.text() == "INCONCLUSIVE"
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
            status="PRECISION_CONFIRMED_12M_10X",
            score=84.5,
            route="F10",
            destination=None,
            confidence=82.0,
        ),
        v12_components={"Core15.3": 81.2},
        v14_components={"M10_D": 78.0, "M10_C": 74.0, "DMG": 4.0},
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
        assert window.v14_page.status.text() == "PRECISION_CONFIRMED_12M_10X"
        assert window.v14_page.score.text() == "84.5 / 100"
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
            resolve_data_path=lambda configured: tmp_path / configured,
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



def test_phase9_scanner_button_fails_closed_without_backend(qapp):
    window = ResearchTerminalWindow()
    try:
        window.scanner_button.click()
        assert window.status.text() == "Scanner backend is not connected"
    finally:
        window.close()


def test_phase9_scanner_dialog_renders_phase7_rows(qapp):
    dialog = MarketScannerDialog(
        scanner_service_factory=lambda: None,
        as_of_date=date(2026, 10, 6),
    )
    try:
        rows = [
            ScanRow(
                security_id="SEC_1",
                ticker="AAA",
                exchange="NASDAQ",
                as_of=datetime(2026, 10, 6, tzinfo=timezone.utc),
                mode=ScanMode.CURRENT,
                v12_score=80.0,
                v12_status="READY",
                v12_route="F10",
                v12_destination=None,
                v14_score=85.0,
                v14_status="READY",
                v14_route="EARLY_ASYMMETRIC",
                v14_destination="3X-5X",
                delisted=False,
            ),
            ScanRow(
                security_id="SEC_2",
                ticker="BBB",
                exchange="NYSE",
                as_of=datetime(2026, 10, 6, tzinfo=timezone.utc),
                mode=ScanMode.CURRENT,
                v12_score=72.0,
                v12_status="READY",
                v12_route="Q10",
                v12_destination=None,
                v14_score=77.0,
                v14_status="READY",
                v14_route="QUALITY",
                v14_destination="2X-5X",
                delisted=False,
            ),
        ]
        summary = ScanSummary(
            mode=ScanMode.CURRENT,
            as_of=datetime(2026, 10, 6, tzinfo=timezone.utc),
            total=2,
            nasdaq=1,
            nyse=1,
            amex=0,
            delisted=0,
        )
        dialog._scan_complete((rows, summary))
        assert dialog.table.rowCount() == 2
        assert "2 rows" in dialog.status.text()
        dialog.exchange.setCurrentText("NASDAQ")
        assert dialog.table.rowCount() == 1
        assert dialog.table.item(0, 0).text() == "AAA"
    finally:
        dialog.close()



def test_phase9_loading_and_error_state_controls(qapp):
    window = ResearchTerminalWindow()
    try:
        window.progress.show()
        window.run_button.setEnabled(False)
        window.scanner_button.setEnabled(False)
        window._analysis_failed("boom")
        assert not window.progress.isVisible()
        assert window.run_button.isEnabled()
        assert window.scanner_button.isEnabled()
        assert window.status.text() == "ERROR — boom"
    finally:
        window.close()


def test_phase9_scanner_loading_and_error_state_controls(qapp):
    dialog = MarketScannerDialog(
        scanner_service_factory=lambda: None,
        as_of_date=date(2026, 10, 6),
    )
    try:
        dialog.progress.show()
        dialog.run_button.setEnabled(False)
        dialog.exchange.setEnabled(False)
        dialog._scan_failed("blocked")
        assert not dialog.progress.isVisible()
        assert dialog.run_button.isEnabled()
        assert dialog.exchange.isEnabled()
        assert dialog.status.text() == "BLOCKED / ERROR — blocked"
        assert dialog.minimumWidth() == 900
    finally:
        dialog.close()



def test_phase9_acceptance_gate_requires_exact_matrix():
    items = [
        UIAcceptanceItem(name=name, passed=True, evidence="tested")
        for name in PHASE9_ACCEPTANCE_ITEMS
    ]
    require_phase9_complete(items)
    assert len(PHASE9_ACCEPTANCE_ITEMS) == 18

    blocked = list(items)
    index = PHASE9_ACCEPTANCE_ITEMS.index("V1.4 canonical active state")
    blocked[index] = UIAcceptanceItem(
        name="V1.4 canonical active state",
        passed=False,
        evidence="canonical V1.4 did not render",
    )
    with pytest.raises(RuntimeError, match="V1.4 canonical active state"):
        require_phase9_complete(blocked)


def test_phase9_computes_single_ticker_historical_backtest_from_adjusted_cache(tmp_path):
    store = SQLiteStore(tmp_path / "ui-backtest.sqlite")
    store.initialize()
    try:
        now = datetime(2026, 10, 7, tzinfo=timezone.utc)
        store.connection.execute(
            """
            INSERT INTO security_master (
                security_id,ticker,name,exchange,market,active,created_at,updated_at
            ) VALUES (?,?,?,?,?,?,?,?)
            """,
            ("SEC_HIST","HIST","History Inc.","NASDAQ","US",1,now.isoformat(),now.isoformat()),
        )
        store.connection.commit()

        start = date(2024, 1, 2)
        bars = []
        for i in range(300):
            day = date.fromordinal(start.toordinal() + i)
            price = 10.0 if i == 0 else 10.0 + i * 0.05
            if i == 120:
                price = 25.0
            bars.append(
                SourcePriceBar(
                    security_id="SEC_HIST",
                    source="YAHOO_COMPAT",
                    source_symbol="HIST",
                    trade_date=day,
                    open=price,
                    high=price,
                    low=price,
                    raw_close=price,
                    adjusted_close=price,
                    volume=1000.0,
                    retrieved_at=now,
                    quality_status=PriceQualityStatus.FALLBACK_ONLY,
                    adjustment_status=AdjustmentStatus.DUAL_RAW_ADJUSTED,
                )
            )

        parquet = ParquetPriceStore(tmp_path / "parquet")
        price_repo = PriceRepository(store, parquet)
        desc = price_repo.save_series(bars)
        price_repo.select_series(
            security_id="SEC_HIST",
            start=desc.start_date,
            end=desc.end_date,
            source=desc.source,
            source_symbol=desc.source_symbol,
            purpose="UI_LIVE_FALLBACK",
            reason="historical-ui-test",
        )

        fake_app = SimpleNamespace(
            sqlite=store,
            app_config=SimpleNamespace(database=SimpleNamespace(parquet_root="parquet")),
            resolve_data_path=lambda configured: tmp_path / configured,
        )

        from app.ui.analysis_service import DesktopAnalysisService
        view = DesktopAnalysisService(tmp_path)._load_backtest(
            fake_app,
            "SEC_HIST",
            start,
        )
        assert view.status == "READY"
        assert view.entry_price == pytest.approx(10.0)
        assert view.horizon_sessions_available == 252
        assert view.fm252 is not None
        assert view.max_multiple_observed is not None
        assert view.time_to_2x_sessions is not None
    finally:
        store.close()

# v1.0.3 UI/backtest regression coverage
