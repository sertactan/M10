from __future__ import annotations

from PySide6.QtWidgets import QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from app.ui.view_models import ComparisonView


class ComparePage(QWidget):
    METRICS = ("Score", "Route", "Destination", "Confidence", "Risk")

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.table = QTableWidget(len(self.METRICS), 3)
        self.table.setHorizontalHeaderLabels(["Metric", "V1.2", "V1.4.1"])
        layout.addWidget(self.table)

        self.consensus = QLabel("MODEL CONSENSUS: —")
        self.consensus.setObjectName("Muted")
        self.winner = QLabel("Winner: —")
        self.conviction = QLabel("Combined Conviction: —")
        layout.addWidget(self.consensus)
        layout.addWidget(self.winner)
        layout.addWidget(self.conviction)
        self._seed_metric_labels()

    def _seed_metric_labels(self) -> None:
        for row, metric in enumerate(self.METRICS):
            self.table.setItem(row, 0, QTableWidgetItem(metric))
            self.table.setItem(row, 1, QTableWidgetItem("—"))
            self.table.setItem(row, 2, QTableWidgetItem("—"))

    @staticmethod
    def _value(view, metric: str) -> str:
        attr = {
            "Score": "score",
            "Route": "route",
            "Destination": "destination",
            "Confidence": "confidence",
            "Risk": "risk",
        }[metric]
        value = getattr(view, attr)
        if value is None:
            return "—"
        if metric == "Score":
            return f"{float(value):.1f}"
        if metric == "Confidence":
            return f"{float(value):.1f}%"
        return str(value)

    def set_comparison(self, view: ComparisonView) -> None:
        for row, metric in enumerate(self.METRICS):
            self.table.setItem(row, 1, QTableWidgetItem(self._value(view.v12, metric)))
            self.table.setItem(row, 2, QTableWidgetItem(self._value(view.v14, metric)))
        self.consensus.setText(f"MODEL CONSENSUS: {view.consensus or '—'}")
        self.winner.setText(f"Winner: {view.winner or '—'}")
        self.conviction.setText(
            f"Combined Conviction: {view.combined_conviction or '—'}"
        )
