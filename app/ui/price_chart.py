from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from PySide6.QtCharts import QChart, QChartView, QDateTimeAxis, QLineSeries, QValueAxis
from PySide6.QtCore import QDateTime, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QVBoxLayout, QWidget


@dataclass(frozen=True)
class PricePointView:
    trade_date: date
    adjusted_close: float


class HistoricalPriceChart(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.chart = QChart()
        self.chart.setTitle('Historical Adjusted Close')
        self.chart.legend().hide()
        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.chart_view)
        self.setMinimumHeight(240)

    @staticmethod
    def _x(trade_date: date) -> float:
        dt = datetime.combine(trade_date, datetime.min.time(), tzinfo=timezone.utc)
        return dt.timestamp() * 1000.0

    def set_series(self, points: list[PricePointView], analysis_date: date) -> None:
        self.chart.removeAllSeries()
        for axis in list(self.chart.axes()):
            self.chart.removeAxis(axis)

        if not points:
            self.chart.setTitle('Historical Adjusted Close — NOT AVAILABLE')
            return

        ordered = sorted(points, key=lambda p: p.trade_date)
        price_series = QLineSeries()
        price_series.setName('Adjusted Close')
        for point in ordered:
            price_series.append(self._x(point.trade_date), point.adjusted_close)
        self.chart.addSeries(price_series)

        x_axis = QDateTimeAxis()
        x_axis.setFormat('yyyy-MM')
        x_axis.setTitleText('Trading Date')
        y_axis = QValueAxis()
        y_axis.setTitleText('Adjusted Close')

        values = [p.adjusted_close for p in ordered]
        low, high = min(values), max(values)
        if low == high:
            low *= 0.95
            high *= 1.05
        margin = max((high - low) * 0.08, 0.01)
        y_axis.setRange(max(0.0, low - margin), high + margin)

        start_dt = QDateTime.fromSecsSinceEpoch(int(self._x(ordered[0].trade_date) / 1000), Qt.UTC)
        end_dt = QDateTime.fromSecsSinceEpoch(int(self._x(ordered[-1].trade_date) / 1000), Qt.UTC)
        x_axis.setRange(start_dt, end_dt)

        self.chart.addAxis(x_axis, Qt.AlignBottom)
        self.chart.addAxis(y_axis, Qt.AlignLeft)
        price_series.attachAxis(x_axis)
        price_series.attachAxis(y_axis)

        if ordered[0].trade_date <= analysis_date <= ordered[-1].trade_date:
            marker = QLineSeries()
            marker.setName('Analysis Date')
            x = self._x(analysis_date)
            marker.append(x, max(0.0, low - margin))
            marker.append(x, high + margin)
            self.chart.addSeries(marker)
            marker.attachAxis(x_axis)
            marker.attachAxis(y_axis)

        self.chart.setTitle(
            f'Historical Adjusted Close · Analysis Date {analysis_date.isoformat()}'
        )
