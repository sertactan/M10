from __future__ import annotations

"""M10 data control dashboard. Manual refresh; asynchronous LOCAL read-only SQL."""
from datetime import timezone
from typing import Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)


class _ReadSignals(QObject):
    loaded = Signal(object)
    failed = Signal(str)


class _ReadTask(QRunnable):
    def __init__(self, factory: Callable[[], object]) -> None:
        super().__init__()
        self.factory = factory
        self.signals = _ReadSignals()

    def run(self) -> None:
        try:
            snapshot = self.factory().snapshot()
        except Exception as exc:
            # No sensitive vendor response or credentials should be included
            # in the user-visible error; show only the exception class.
            self.signals.failed.emit(type(exc).__name__)
        else:
            self.signals.loaded.emit(snapshot)


class DataControlCenterDialog(QDialog):
    def __init__(self, *, service_factory: Callable[[], object] | None,
                 parent=None, auto_load: bool = True) -> None:
        super().__init__(parent)
        self.service_factory = service_factory
        self._task: _ReadTask | None = None
        self.setWindowTitle("Meridyen — Data Control Center (Read Only)")
        self.resize(1080, 680)
        self.setMinimumSize(860, 550)
        root = QVBoxLayout(self)

        header = QHBoxLayout()
        self.title = QLabel("MERIDYEN — DATA CONTROL CENTER")
        self.title.setObjectName("AppTitle")
        header.addWidget(self.title, 1)
        self.refresh_button = QPushButton("REFRESH (READ ONLY)")
        self.refresh_button.clicked.connect(self.refresh)
        header.addWidget(self.refresh_button)
        root.addLayout(header)

        self.summary = QLabel("No snapshot loaded")
        self.summary.setObjectName("Muted")
        root.addWidget(self.summary)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Area", "Measured Value", "Interpretation"])
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.table, 1)

        self.blockers = QLabel("Awaiting read-only inspection")
        self.blockers.setWordWrap(True)
        self.blockers.setObjectName("Muted")
        root.addWidget(self.blockers)

        self.disclaimer = QLabel(
            "Counts ≠ PIT certification. No trading data is downloaded, no "
            "SEC import interrupted, no canonical score or WF9 activation produced."
        )
        self.disclaimer.setWordWrap(True)
        self.disclaimer.setObjectName("Muted")
        root.addWidget(self.disclaimer)

        self.status = QLabel("READY — manual refresh only")
        self.status.setObjectName("Muted")
        root.addWidget(self.status)

        if auto_load and self.service_factory is not None:
            self.refresh()

    def refresh(self) -> None:
        if self.service_factory is None:
            self.status.setText("Data Control Center backend is not connected")
            return
        if self._task is not None:
            return
        self.refresh_button.setEnabled(False)
        self.status.setText("Reading local SQLite only (SEC import not interrupted)...")
        task = _ReadTask(self.service_factory)
        self._task = task
        task.signals.loaded.connect(self.apply_snapshot)
        task.signals.failed.connect(self._failed)
        task.signals.loaded.connect(self._finished)
        task.signals.failed.connect(self._finished)
        QThreadPool.globalInstance().start(task)

    def _failed(self, error_class: str) -> None:
        self.status.setText("READ_ONLY_BLOCKED — " + error_class + " (retry after SEC workload)")

    def _finished(self, _result) -> None:
        self.refresh_button.setEnabled(True)
        self._task = None

    @staticmethod
    def _value(value: int | None) -> str:
        return f"{value:,}" if value is not None else "NOT AVAILABLE"

    def apply_snapshot(self, view) -> None:
        self.summary.setText(
            "LOCAL READ ONLY — "
            + view.observed_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        )
        rows = [
            ("Historical PIT listings",
             (f"{view.pit_present}/{view.pit_target}" if view.pit_present is not None
              else "NOT AVAILABLE"),
             "Next missing: " + (view.first_missing_month or "—")),
            ("SEC CIK-mapped US securities", self._value(view.sec_cik_mapped_us),
             "CIK match count; not SEC PIT validation"),
            ("SEC EDGAR fact records", self._value(view.sec_fact_rows),
             "Rows imported; status of running SEC job not verified"),
            ("Price series", self._value(view.price_series),
             "All sources; includes incomplete/pilot"),
            ("Adjusted price series", self._value(view.adjusted_series),
             "Reported adjustment flags, not independent verification"),
            ("Reported adjusted bar rows", self._value(view.reported_adjusted_bar_rows),
             "Registry sum; not trading-session coverage"),
            ("Split events", self._value(view.split_event_rows),
             "Stored source records"),
            ("Dividend events", self._value(view.dividend_event_rows),
             "Stored source records"),
            ("Unverified price pilots", self._value(view.pilot_price_selections),
             "Must not be treated as canonical backtest prices"),
            ("Canonical adjusted selections", self._value(view.backtest_adjusted_selections),
             "Selections only; physical bar/delisting audits needed"),
            ("WF5 replay runs", self._value(view.wf5_run_rows),
             "Run rows; success not guaranteed"),
            ("WF6 walk-forward runs", self._value(view.wf6_run_rows),
             "Run rows; OOS status not guaranteed"),
            ("WF8 activation records", self._value(view.wf8_activation_rows),
             "Not evidence of WF9 activation"),
            ("Daily PIT automation", view.pit_daily_status,
             "UTC date: " + (view.pit_daily_date_utc or "—")),
            ("WF9 production verified", "NO",
             "This diagnostic cannot certify or activate WF9"),
        ]
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, value in enumerate(row):
                self.table.setItem(i, j, QTableWidgetItem(str(value)))
        self.table.resizeColumnsToContents()
        self.blockers.setText(
            "READINESS BLOCKERS: "
            + (" | ".join(view.blockers) if view.blockers else
               "No blockers in these lightweight counts; run native readiness audits")
        )
        self.status.setText("OK — local diagnostic snapshot only, no database writes")
