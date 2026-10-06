from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.ui.price_chart import HistoricalPriceChart, PricePointView
from app.ui.view_models import ModelView


def _fmt(value) -> str:
    return "—" if value is None else str(value)


class ModelPage(QWidget):
    def __init__(self, model_name: str, parent=None) -> None:
        super().__init__(parent)
        self.model_name = model_name

        root = QVBoxLayout(self)
        cards = QHBoxLayout()

        score_card = QFrame()
        score_card.setObjectName("Card")
        score_layout = QVBoxLayout(score_card)
        score_layout.addWidget(QLabel(model_name))
        self.score = QLabel("—")
        self.score.setObjectName("Score")
        score_layout.addWidget(self.score)
        self.status = QLabel("NOT LOADED")
        self.status.setObjectName("Muted")
        score_layout.addWidget(self.status)
        cards.addWidget(score_card, 2)

        detail_card = QFrame()
        detail_card.setObjectName("Card")
        details = QGridLayout(detail_card)
        self.route = QLabel("—")
        self.destination = QLabel("—")
        self.confidence = QLabel("—")
        self.risk = QLabel("—")
        for row, (name, widget) in enumerate((
            ("Route", self.route),
            ("Destination", self.destination),
            ("Confidence", self.confidence),
            ("Risk", self.risk),
        )):
            label = QLabel(name)
            label.setObjectName("Muted")
            details.addWidget(label, row, 0)
            details.addWidget(widget, row, 1)
        cards.addWidget(detail_card, 3)
        root.addLayout(cards)

        self.components = QTableWidget(0, 2)
        self.components.setHorizontalHeaderLabels(["Metric", "Value"])
        self.components.setAlternatingRowColors(True)
        root.addWidget(self.components, 1)
        self.price_chart = HistoricalPriceChart()
        root.addWidget(self.price_chart)

    def set_model(self, view: ModelView, components: dict[str, object] | None = None) -> None:
        self.status.setText(view.status)
        self.score.setText("—" if view.score is None else f"{view.score:.1f} / 100")
        self.route.setText(_fmt(view.route))
        self.destination.setText(_fmt(view.destination))
        self.confidence.setText(
            "—" if view.confidence is None else f"{view.confidence:.1f}%"
        )
        self.risk.setText(_fmt(view.risk))

        items = sorted((components or {}).items())
        self.components.setRowCount(len(items))
        for row, (name, value) in enumerate(items):
            self.components.setItem(row, 0, QTableWidgetItem(str(name)))
            self.components.setItem(row, 1, QTableWidgetItem(_fmt(value)))

    def set_price_series(self, points: list[PricePointView], analysis_date) -> None:
        self.price_chart.set_series(points, analysis_date)
