"""Read-only historical source/PIT/backtest readiness window (no train button)."""
from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)


def format_historical_pit_view(view) -> list[tuple[str, str]]:
    """Pure formatting so the headless CI can assert honest status text."""
    def num(value):
        return "NOT VERIFIED" if value is None else f"{value:,}"
    return [
        ("Period", view.period),
        ("Evidence state", view.state),
        ("Phase25Q staging version", view.staging_version or "NOT AVAILABLE"),
        ("Month-end source snapshots", num(view.member_months)),
        ("Research source member rows", num(view.membership_rows)),
        ("Raw SimFin source daily price rows", num(view.source_price_rows)),
        ("Phase25R independently reconciled source price rows",
         num(view.independently_reconciled_price_rows)),
        ("Strong source candidates", num(view.strong_source_candidates)),
        ("Conflicting month/issuer identity rows", num(view.conflicting_source_identity_rows)),
        ("Strong candidate affected tickers",
         ", ".join(view.affected_strong_tickers) or "NOT VERIFIED"),
        ("SITC SEC-documented issuer actions", num(view.sitc_issuer_actions)),
        ("SITC real source pre/post price pairs", num(view.sitc_real_price_pairs)),
        ("Independently canonical-approved securities", num(view.canonical_securities)),
        ("Real WF9 walk-forward", view.wf9),
        ("Real Learning V3 training", view.learning_v3),
    ]


class HistoricalPitEvidenceDialog(QDialog):
    def __init__(self, *, service_factory: Callable[[], object], parent=None,
                 auto_load=True):
        super().__init__(parent)
        self.service_factory = service_factory
        self.setWindowTitle("Meridyen M10 — Historical PIT / Learning V3 (READ ONLY)")
        self.resize(920, 670)
        root = QVBoxLayout(self)
        header = QHBoxLayout()
        self.title = QLabel("HISTORICAL PIT / LEARNING V3 — EVIDENCE ONLY")
        self.title.setObjectName("AppTitle")
        header.addWidget(self.title, 1)
        self.refresh_button = QPushButton("REFRESH (NO MODEL TRAINING)")
        self.refresh_button.clicked.connect(self.refresh)
        header.addWidget(self.refresh_button)
        root.addLayout(header)
        self.status = QLabel("NO CERTIFICATION HAS BEEN INFERRED")
        self.status.setObjectName("Muted")
        root.addWidget(self.status)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Evidence control", "Observed result"])
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.table, 1)
        self.blockers = QLabel("Awaiting local, read-only source report inspection")
        self.blockers.setWordWrap(True)
        self.blockers.setObjectName("Muted")
        root.addWidget(self.blockers)
        self.note = QLabel(
            "Caution: retrospective vendor source prices and issuer SEC action documents "
            "do not constitute PIT-adjusted, delisting-complete returns. "
            "This screen never starts WF9 or Learning V3."
        )
        self.note.setWordWrap(True)
        root.addWidget(self.note)
        if auto_load:
            self.refresh()

    def refresh(self) -> None:
        try:
            view = self.service_factory().snapshot()
        except (OSError, ValueError, TypeError):
            self.status.setText("EVIDENCE ACCESS ERROR — no canonical approval")
            return
        values = format_historical_pit_view(view)
        self.table.setRowCount(len(values))
        for row, (name, value) in enumerate(values):
            self.table.setItem(row, 0, QTableWidgetItem(name))
            self.table.setItem(row, 1, QTableWidgetItem(value))
        self.table.resizeColumnsToContents()
        self.status.setText(
            f"{view.state} — {view.wf9} — {view.learning_v3}"
        )
        self.blockers.setText(
            "UNRESOLVED EVIDENCE REQUIREMENTS:\n• " +
            "\n• ".join(view.blockers)
        )
