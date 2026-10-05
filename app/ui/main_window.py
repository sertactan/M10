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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.ui.analysis_worker import AnalysisTask
from app.ui.compare_page import ComparePage
from app.ui.model_page import ModelPage
from app.ui.view_models import ComparisonView


class ResearchTerminalWindow(QMainWindow):
    analysis_requested = Signal(str, object)

    def __init__(
        self,
        *,
        analysis_service_factory: Callable[[], object] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.analysis_service_factory = analysis_service_factory
        self.thread_pool = QThreadPool.globalInstance()
        self.setWindowTitle("S15.3 Research Terminal")
        self.resize(1440, 900)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.addWidget(self._build_header())

        self.tabs = QTabWidget()
        self.v12_page = ModelPage("S15.3 V1.2")
        self.v14_page = ModelPage("S15.3 V1.4")
        self.compare_page = ComparePage()
        self.tabs.addTab(self.v12_page, "V1.2")
        self.tabs.addTab(self.v14_page, "V1.4")
        self.tabs.addTab(self.compare_page, "COMPARE")
        root.addWidget(self.tabs, 1)

        self.status = QLabel("READY — no analysis loaded")
        self.status.setObjectName("Muted")
        root.addWidget(self.status)

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

        self.run_button = QPushButton("RUN ANALYSIS")
        self.run_button.clicked.connect(self._run_analysis)
        layout.addWidget(self.run_button)
        return frame

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
        self.v12_page.set_model(result.v12, result.v12_components)
        self.v14_page.set_model(result.v14, result.v14_components)
        self.compare_page.set_comparison(
            ComparisonView(v12=result.v12, v14=result.v14)
        )
        self.status.setText(
            f"LOADED {result.ticker} @ {result.as_of.date().isoformat()}"
        )
        self.run_button.setEnabled(True)

    def _analysis_failed(self, message: str) -> None:
        self.status.setText(f"ERROR — {message}")
        self.run_button.setEnabled(True)
