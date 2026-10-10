"""Phase27 current scoring research pane; opt-in and never production/canonical."""
from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from app.phase27_current_scoring import check_ticker, run_pilot


class _Events(QObject):
    success = Signal(dict)
    failed = Signal(str)


class _ResearchTask(QRunnable):
    def __init__(self, db_path: Path, archive: Path, ticker: str) -> None:
        super().__init__()
        self.db_path, self.archive, self.ticker = db_path, archive, ticker
        self.events = _Events()

    def run(self) -> None:
        try:
            self.events.success.emit(run_pilot(self.db_path, self.archive, self.ticker))
        except Exception as exc:
            self.events.failed.emit(f"{type(exc).__name__}: {exc}")


class Phase27CurrentPage(QWidget):
    """No implicit network calls: fetching requires explicit enter or button."""

    def __init__(self, db_path: Path, archive: Path | None = None, parent=None,
                 *, phase28_db: Path | None = None):
        super().__init__(parent)
        self.db_path, self.archive = Path(db_path), Path(archive) if archive else None
        self.phase28_db = Path(phase28_db) if phase28_db else None
        self._task: _ResearchTask | None = None
        self._pool = QThreadPool.globalInstance()
        self._details: dict[str, dict] = {}
        root = QVBoxLayout(self)
        self.warning = QLabel(
            "FAZ 27 · CURRENT RESEARCH ONLY · Yahoo-compatible delayed/last trade; "
            "cached SEC accepted_at unverified · CANONICAL 0/0 · WF9 BLOCKED · "
            "Learning V3 NOT_TRAINED"
        )
        self.warning.setWordWrap(True)
        root.addWidget(self.warning)
        header = QHBoxLayout()
        self.ticker = QLineEdit()
        self.ticker.setPlaceholderText("INOD / TMDX / CRMD / PENG / ETON")
        self.ticker.setMaxLength(12)
        self.ticker.returnPressed.connect(self.fetch)
        header.addWidget(self.ticker)
        self.fetch_button = QPushButton("FETCH (phase27 staging only)")
        self.fetch_button.clicked.connect(self.fetch)
        header.addWidget(self.fetch_button)
        self.cached_button = QPushButton("LOAD CACHED (offline)")
        self.cached_button.clicked.connect(self._cached_clicked)
        header.addWidget(self.cached_button)
        root.addLayout(header)
        self.summary = QLabel("No verified current research report loaded")
        self.summary.setWordWrap(True)
        root.addWidget(self.summary)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(("Model", "Score", "Status", "Coverage"))
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self.show_details)
        root.addWidget(self.table, 2)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setPlaceholderText("Click a model to view exact missing inputs and source evidence.")
        root.addWidget(self.details, 1)

    def fetch(self) -> None:
        try:
            ticker = check_ticker(self.ticker.text())
        except ValueError as exc:
            self.summary.setText(str(exc))
            return
        if self.archive is None:
            self.summary.setText("M10_PHASE27_HISTORICAL_ARCHIVE not configured; no source reads allowed")
            return
        if self._task is not None:
            self.summary.setText("IN_PROGRESS · bounded provider request still running")
            return
        self.fetch_button.setEnabled(False)
        self.summary.setText(f"IN_PROGRESS · {ticker} · bounded Yahoo request")
        task = _ResearchTask(self.db_path, self.archive, ticker)
        self._task = task
        task.events.success.connect(self._loaded)
        task.events.failed.connect(self._failed)
        self._pool.start(task)

    def _failed(self, reason: str) -> None:
        self._task = None
        self.fetch_button.setEnabled(True)
        self.summary.setText("PROVIDER_ERROR / INCONCLUSIVE · " + reason)

    def _cached_clicked(self) -> None:
        try:
            self.load_cached(self.ticker.text())
        except (ValueError, sqlite3.DatabaseError, OSError) as exc:
            self.summary.setText("MISSING_DATA · " + str(exc))

    def _loaded(self, report: dict) -> None:
        self._task = None
        self.fetch_button.setEnabled(True)
        self._show_report(report)

    def load_cached(self, ticker: str) -> bool:
        """Read-only UI refresh; no implicit create, fetch, or live DB access."""
        if not self.db_path.is_file() or self.db_path.is_symlink():
            self.summary.setText("MISSING_DATA · Phase27 staging report not found")
            return False
        with closing(sqlite3.connect(self.db_path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
            row = db.execute("SELECT details_json FROM stock_runs WHERE ticker=?", (check_ticker(ticker),)).fetchone()
        if row is None:
            self.summary.setText("MISSING_DATA · No staged report for " + ticker)
            return False
        self.ticker.setText(ticker)
        self._show_report(json.loads(row[0]))
        return True

    def _show_report(self, report: dict) -> None:
        ticker = report["ticker"]
        price = report["price"]
        price_text = f"{price:.2f} {report['currency']}" if price is not None else "N/A"
        self.summary.setText(
            f"{ticker} · {price_text} · trade {report['trade_date']} · "
            f"market timestamp {report['quote_time']} · {report['quote_status']} · "
            f"finance {report['financial_status']} / {report['financial_period']} · "
            f"{report['bars']} OHLCV · {report['raw_research_features']} research features"
        )
        self.table.setRowCount(0)
        self._details = {}
        overlay = self._read_phase28(report)
        audits = overlay.get("models", report["model_audits"]) if overlay else report["model_audits"]
        if overlay:
            self.summary.setText(
                self.summary.text() + " · PHASE28 "
                + f"{overlay['phase28_feature_count']} sourced finance/quality features; "
                + f"FULL S1-S16 {overlay['full_model_score_count']} (research scoring acceptance)"
            )
            self.warning.setText(
                "PHASE28 · CURRENT RESEARCH ONLY · SEC accepted_at NOT VERIFIED · "
                "PARTIAL FINANCIAL COMPONENTS ARE NOT FULL SCORES · "
                "Historical Canonical 0/0 · WF9 BLOCKED · Learning V3 NOT_TRAINED"
            )
        for audit in audits:
            i = self.table.rowCount()
            self.table.insertRow(i)
            self._details[audit["model"]] = audit
            coverage = audit.get("coverage_pct", audit.get("coverage"))
            for col, value in enumerate((
                audit["model"], "N/A" if audit["score"] is None else f"{audit['score']:.2f}",
                audit["status"], f"{coverage:.1f}%" if coverage is not None else "N/A",
            )):
                self.table.setItem(i, col, QTableWidgetItem(value))
        self.details.setPlainText(
            "Source: " + report["price_provider"] + " · SHA-256 " + report["price_payload_sha256"]
            + "\nResearch-only derived features: "
            + json.dumps(report["research_features"], sort_keys=True)
            + ("\nPHASE28 (RESEARCH_ONLY): " + json.dumps(
                 {"financial_features":overlay["features"],
                  "partial_component_diagnostics":overlay["diagnostics"]},
                 ensure_ascii=False, sort_keys=True) if overlay else "")
        )

    def _read_phase28(self, source_report: dict) -> dict | None:
        """Optional, offline, read-only upgrade to the *existing* Phase27 page."""
        stage = self.phase28_db
        if not stage or not stage.is_file() or stage.is_symlink():
            return None
        if "phase28" not in {part.casefold() for part in stage.resolve().parts}:
            return None
        try:
            with closing(sqlite3.connect(stage.resolve().as_uri() + "?mode=ro",
                                         uri=True, timeout=3)) as db:
                row = db.execute(
                    "SELECT report_json FROM phase28_runs WHERE ticker=?",
                    (source_report["ticker"],)
                ).fetchone()
                if row is None:
                    return None
                result = json.loads(row[0])
                # A stale Phase28 snapshot must not overwrite changed Phase27
                # quotes or identities with mismatched price records.
                if result.get("ticker") != source_report["ticker"] or (
                        result.get("price_time") != source_report["quote_time"]):
                    return None
                return result
        except (ValueError, sqlite3.DatabaseError, OSError, KeyError):
            return None

    def show_details(self) -> None:
        row = self.table.currentRow()
        if row < 0 or not self.table.item(row, 0):
            return
        name = self.table.item(row, 0).text()
        if name in self._details:
            self.details.setPlainText(json.dumps(self._details[name], indent=2, ensure_ascii=False))
