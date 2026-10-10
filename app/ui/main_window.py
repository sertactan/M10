from __future__ import annotations

from datetime import date
from typing import Callable

from PySide6.QtCore import QDate, QThreadPool, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QProgressBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.ui.analysis_worker import AnalysisTask
from app.ui.compare_page import ComparePage
from app.ui.context_panels import AnalysisContextPanel, StockHeaderPanel
from app.ui.data_health_dialog import DataHealthDialog
from app.ui.historical_pit_evidence_dialog import HistoricalPitEvidenceDialog
from app.ui.data_control_center_dialog import DataControlCenterDialog
from app.ui.model_page import ModelPage
from app.ui.scanner_dialog import MarketScannerDialog
from app.ui.view_models import ComparisonView


class ResearchTerminalWindow(QMainWindow):
    analysis_requested = Signal(str, object)

    def __init__(
        self,
        *,
        analysis_service_factory: Callable[[], object] | None = None,
        scanner_service_factory: Callable[[], object] | None = None,
        data_health_service_factory: Callable[[], object] | None = None,
        control_center_service_factory: Callable[[], object] | None = None,
        historical_pit_service_factory: Callable[[], object] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.analysis_service_factory = analysis_service_factory
        self.scanner_service_factory = scanner_service_factory
        self.data_health_service_factory = data_health_service_factory
        self.control_center_service_factory = control_center_service_factory
        self.historical_pit_service_factory = historical_pit_service_factory
        self.thread_pool = QThreadPool.globalInstance()
        self.setWindowTitle("S15.3 Research Terminal")
        self.resize(1440, 900)
        self.setMinimumSize(1100, 700)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.addWidget(self._build_header())
        self.stock_header = StockHeaderPanel()
        root.addWidget(self.stock_header)
        self.context_panel = AnalysisContextPanel()
        root.addWidget(self.context_panel)

        self.tabs = QTabWidget()
        self.v12_page = ModelPage("S15.3 V1.2")
        self.v14_page = ModelPage("S15.3 V1.4.1")
        self.s16_page = ModelPage("S16 V1.0 Canonical")
        self.s16_ea_page = ModelPage("S16-EA V1.3 Canonical Hybrid FastPath")
        self.compare_page = ComparePage()
        self.tabs.addTab(self.v12_page, "V1.2")
        self.tabs.addTab(self.v14_page, "V1.4.1")
        self.tabs.addTab(self.s16_page, "S16")
        self.tabs.addTab(self.s16_ea_page, "S16-EA")
        self.tabs.addTab(self.compare_page, "COMPARE")
        root.addWidget(self.tabs, 1)

        footer = QHBoxLayout()
        self.status = QLabel("READY — no analysis loaded")
        self.status.setObjectName("Muted")
        footer.addWidget(self.status, 1)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setFixedWidth(160)
        self.progress.hide()
        footer.addWidget(self.progress)
        root.addLayout(footer)

    def _build_header(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("Header")
        layout = QHBoxLayout(frame)

        title = QLabel("S15.3 Research Terminal")
        title.setObjectName("AppTitle")
        layout.addWidget(title)

        self.market = QComboBox()
        self.market.addItem("United States")
        self.market.setToolTip("Phase 9 V1 supports the United States only")
        layout.addWidget(self.market)

        self.ticker = QLineEdit()
        self.ticker.setPlaceholderText("Ticker e.g. CRMD")
        self.ticker.setMaxLength(12)
        self.ticker.setMinimumWidth(140)
        self.ticker.returnPressed.connect(self._run_analysis)
        layout.addWidget(self.ticker, 1)

        self.analysis_date = QDateEdit(QDate.currentDate())
        self.analysis_date.setCalendarPopup(True)
        self.analysis_date.setDisplayFormat("yyyy-MM-dd")
        layout.addWidget(self.analysis_date)

        today = QPushButton("TODAY")
        today.clicked.connect(lambda: self.analysis_date.setDate(QDate.currentDate()))
        layout.addWidget(today)

        self.horizon = QComboBox()
        self.horizon.addItem("12 Months", 12)
        layout.addWidget(self.horizon)

        self.data_health_button = QPushButton("DATA HEALTH")
        self.data_health_button.clicked.connect(self._open_data_health)
        layout.addWidget(self.data_health_button)

        self.control_center_button = QPushButton("DATA CONTROL")
        self.control_center_button.clicked.connect(self._open_control_center)
        layout.addWidget(self.control_center_button)

        self.pit_evidence_button = QPushButton("PIT / LEARNING")
        self.pit_evidence_button.clicked.connect(self._open_historical_pit)
        layout.addWidget(self.pit_evidence_button)

        self.scanner_button = QPushButton("MARKET SCANNER")
        self.scanner_button.clicked.connect(self._open_scanner)
        layout.addWidget(self.scanner_button)

        self.run_button = QPushButton("RUN ANALYSIS")
        self.run_button.clicked.connect(self._run_analysis)
        layout.addWidget(self.run_button)
        return frame

    def _open_data_health(self) -> None:
        if self.data_health_service_factory is None:
            self.status.setText("Data health backend is not connected")
            return
        dialog = DataHealthDialog(
            service_factory=self.data_health_service_factory,
            parent=self,
        )
        dialog.setModal(False)
        dialog.show()
        self._data_health_dialog = dialog

    def _open_control_center(self) -> None:
        if self.control_center_service_factory is None:
            self.status.setText("Data Control Center backend is not connected")
            return
        dialog = DataControlCenterDialog(
            service_factory=self.control_center_service_factory,
            parent=self,
        )
        dialog.setModal(False)
        dialog.show()
        self._control_center_dialog = dialog

    def _open_historical_pit(self) -> None:
        if self.historical_pit_service_factory is None:
            self.status.setText("Historical PIT evidence service is not connected")
            return
        dialog = HistoricalPitEvidenceDialog(
            service_factory=self.historical_pit_service_factory,
            parent=self,
        )
        dialog.setModal(False)
        dialog.show()
        self._historical_pit_dialog = dialog

    def _open_scanner(self) -> None:
        if self.scanner_service_factory is None:
            self.status.setText('Scanner backend is not connected')
            return
        dialog = MarketScannerDialog(
            scanner_service_factory=self.scanner_service_factory,
            as_of_date=self.analysis_date.date().toPython(),
            parent=self,
        )
        dialog.setModal(False)
        dialog.show()
        self._scanner_dialog = dialog
    def _run_analysis(self) -> None:
        ticker = self.ticker.text().strip().upper()
        if not ticker:
            self.status.setText("Ticker is required")
            return
        as_of = self.analysis_date.date().toPython()
        self.analysis_requested.emit(ticker, as_of)

        if self.analysis_service_factory is None:
            self.status.setText("Analysis backend is not connected")
            return

        self.run_button.setEnabled(False)
        self.scanner_button.setEnabled(False)
        self.progress.show()
        self.status.setText(f"ANALYZING {ticker} @ {as_of.isoformat()} …")
        task = AnalysisTask(
            self.analysis_service_factory,
            ticker=ticker,
            as_of_date=as_of,
        )
        task.signals.completed.connect(self._apply_analysis)
        task.signals.failed.connect(self._analysis_failed)
        self.thread_pool.start(task)

    def _apply_analysis(self, result) -> None:
        self.stock_header.set_stock(result.stock)
        self.context_panel.set_backtest(result.backtest)
        self.context_panel.set_forecast(result.forecast)
        self.v12_page.set_model(result.v12, result.v12_components)
        self.v14_page.set_model(result.v14, result.v14_components)
        self.s16_page.set_model(result.s16, result.s16_components)
        self.s16_ea_page.set_model(result.s16_ea, result.s16_ea_components)
        self.v12_page.set_price_series(result.price_points, result.as_of.date())
        self.v14_page.set_price_series(result.price_points, result.as_of.date())
        self.s16_page.set_price_series(result.price_points, result.as_of.date())
        self.s16_ea_page.set_price_series(result.price_points, result.as_of.date())
        self.compare_page.set_comparison(
            ComparisonView(v12=result.v12, v14=result.v14)
        )
        self.status.setText(
            f"LOADED {result.ticker} @ {result.as_of.date().isoformat()}"
        )
        self.progress.hide()
        self.run_button.setEnabled(True)
        self.scanner_button.setEnabled(True)

    def _analysis_failed(self, message: str) -> None:
        self.status.setText(f"ERROR — {message}")
        self.progress.hide()
        self.run_button.setEnabled(True)
        self.scanner_button.setEnabled(True)
