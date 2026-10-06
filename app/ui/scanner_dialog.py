from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QPushButton,
    QProgressBar, QTableWidget, QTableWidgetItem, QVBoxLayout
)

from core.scanner.resultset import export_csv


class ScannerSignals(QObject):
    completed = Signal(object)
    failed = Signal(str)
    progress = Signal(object)


class ScannerTask(QRunnable):
    def __init__(self, factory: Callable[[], object], as_of_date: date) -> None:
        super().__init__()
        self.factory = factory
        self.as_of_date = as_of_date
        self.signals = ScannerSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self.factory().scan(
                as_of_date=self.as_of_date,
                on_progress=self.signals.progress.emit,
            )
        except Exception as exc:
            self.signals.failed.emit(str(exc))
            return
        self.signals.completed.emit(result)


class MarketScannerDialog(QDialog):
    COLUMNS = ('Ticker','Exchange','DNA60','V1.2','V1.4','V1.2 Route','V1.4 Route','Missing','Delisted')

    def __init__(self, *, scanner_service_factory: Callable[[], object], as_of_date: date, parent=None) -> None:
        super().__init__(parent)
        self.scanner_service_factory = scanner_service_factory
        self.as_of_date = as_of_date
        self.rows = []
        self.thread_pool = QThreadPool.globalInstance()
        self.setWindowTitle('Market Scanner')
        self.resize(1100, 700)
        self.setMinimumSize(900, 560)

        root = QVBoxLayout(self)
        controls = QHBoxLayout()
        self.exchange = QComboBox()
        self.exchange.addItems(['ALL','NASDAQ','NYSE','AMEX'])
        controls.addWidget(self.exchange)
        self.run_button = QPushButton('RUN SCAN')
        self.run_button.clicked.connect(self.run_scan)
        controls.addWidget(self.run_button)
        self.export_button = QPushButton('EXPORT CSV')
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self.export_results)
        controls.addWidget(self.export_button)
        self.status = QLabel('READY')
        controls.addWidget(self.status, 1)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setFixedWidth(140)
        self.progress.setRange(0, 0)
        self.progress.hide()
        controls.addWidget(self.progress)
        root.addLayout(controls)

        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(list(self.COLUMNS))
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.table, 1)
        self.exchange.currentTextChanged.connect(self._render)

    def run_scan(self) -> None:
        self.run_button.setEnabled(False)
        self.export_button.setEnabled(False)
        self.exchange.setEnabled(False)
        self.progress.show()
        self.status.setText(f'SCANNING @ {self.as_of_date.isoformat()} …')
        task = ScannerTask(self.scanner_service_factory, self.as_of_date)
        task.signals.completed.connect(self._scan_complete)
        task.signals.failed.connect(self._scan_failed)
        task.signals.progress.connect(self._scan_progress)
        self.thread_pool.start(task)

    def _scan_progress(self, progress) -> None:
        total = max(0, int(getattr(progress, 'total', 0) or 0))
        completed = max(0, int(getattr(progress, 'completed', 0) or 0))
        ticker = getattr(progress, 'last_ticker', None)
        if total > 0:
            self.progress.setRange(0, total)
            self.progress.setValue(min(completed, total))
            suffix = f' · {ticker}' if ticker else ''
            self.status.setText(
                f'SCANNING {completed:,}/{total:,} @ {self.as_of_date.isoformat()}{suffix}'
            )
        else:
            self.progress.setRange(0, 0)

    def _scan_complete(self, result) -> None:
        rows, summary = result
        self.rows = list(rows)
        v12_scored = max(
            int(summary.v12_scored),
            sum(1 for row in self.rows if row.v12_score is not None),
        )
        v14_scored = max(
            int(summary.v14_scored),
            sum(1 for row in self.rows if row.v14_score is not None),
        )
        notes = tuple(getattr(summary, 'notes', ()) or ())
        note_text = ' · '.join(notes[-2:])
        if v12_scored == 0 and v14_scored == 0:
            base = f'{summary.total} rows · final scored 0'
            if note_text:
                base += f' · {note_text}'
            else:
                base += ' · canonical feature cache is empty'
            self.status.setText(base)
        else:
            base = (
                f'{summary.total} rows · V1.2 scored {v12_scored} · '
                f'V1.4 scored {v14_scored} · NASDAQ {summary.nasdaq} · '
                f'NYSE {summary.nyse} · AMEX {summary.amex}'
            )
            if note_text:
                base += f' · {note_text}'
            self.status.setText(base)
        self.progress.hide()
        self.run_button.setEnabled(True)
        self.exchange.setEnabled(True)
        self.export_button.setEnabled(bool(self.rows))
        self._render()

    def _scan_failed(self, message: str) -> None:
        if "No canonical historical universe snapshot" in message:
            message = (
                "Historical PIT universe snapshot is not installed for this date; "
                "current-universe substitution is forbidden by strict PIT"
            )
        self.status.setText(f'BLOCKED / ERROR — {message}')
        self.progress.hide()
        self.run_button.setEnabled(True)
        self.exchange.setEnabled(True)
        self.export_button.setEnabled(bool(self.rows))

    def _render(self) -> None:
        exchange = self.exchange.currentText()
        rows = self.rows if exchange == 'ALL' else [r for r in self.rows if r.exchange == exchange]
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            dna60 = row.metadata.get('dna60')
            missing = row.metadata.get('v12_missing') or ()
            values = (
                row.ticker,
                row.exchange,
                '—' if dna60 is None else f'{float(dna60):.1f}',
                '—' if row.v12_score is None else f'{row.v12_score:.1f}',
                '—' if row.v14_score is None else f'{row.v14_score:.1f}',
                row.v12_route or '—',
                row.v14_route or '—',
                ', '.join(str(item) for item in missing) if missing else '—',
                'YES' if row.delisted else 'NO',
            )
            for column, value in enumerate(values):
                self.table.setItem(index, column, QTableWidgetItem(str(value)))
        self.table.setSortingEnabled(True)

    def export_results(self) -> None:
        if not self.rows:
            return
        path, _ = QFileDialog.getSaveFileName(self, 'Export Scanner Results', 'scanner.csv', 'CSV (*.csv)')
        if not path:
            return
        export_csv(self.rows, Path(path))
        self.status.setText(f'EXPORTED · {path}')
