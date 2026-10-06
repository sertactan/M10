from __future__ import annotations

from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.ui.view_models import BacktestView, ForecastView, StockHeaderView


def _num(value: float | None, suffix: str = '', decimals: int = 1) -> str:
    if value is None:
        return '—'
    return f'{value:.{decimals}f}{suffix}'


class StockHeaderPanel(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName('Card')
        layout = QHBoxLayout(self)

        identity = QVBoxLayout()
        self.ticker = QLabel('—')
        self.ticker.setObjectName('AppTitle')
        self.name = QLabel('No security loaded')
        self.name.setObjectName('Muted')
        identity.addWidget(self.ticker)
        identity.addWidget(self.name)
        layout.addLayout(identity, 2)

        self.exchange = QLabel('—')
        self.price = QLabel('—')
        self.price.setObjectName('Score')
        self.change = QLabel('—')
        self.source = QLabel('PRICE NOT LOADED')
        self.source.setObjectName('Muted')
        for widget in (self.exchange, self.price, self.change, self.source):
            layout.addWidget(widget)

    def set_stock(self, view: StockHeaderView) -> None:
        self.ticker.setText(view.ticker)
        self.name.setText(view.name)
        self.exchange.setText(view.exchange)
        self.price.setText('—' if view.price is None else f'${view.price:,.2f}')
        if view.change_pct is None:
            self.change.setText('—')
        else:
            self.change.setText(f'{view.change_pct:+.2f}%')
        source = view.status
        if view.price_source:
            source += f' · {view.price_source}'
        if view.price_date:
            source += f' · {view.price_date}'
        self.source.setText(source)


class AnalysisContextPanel(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.backtest_card = QFrame()
        self.backtest_card.setObjectName('Card')
        backtest = QGridLayout(self.backtest_card)
        self.backtest_status = QLabel('NOT AVAILABLE')
        self.backtest_status.setObjectName('Muted')
        self.backtest_values = {}
        backtest.addWidget(QLabel('Historical Backtest'), 0, 0)
        backtest.addWidget(self.backtest_status, 0, 1)
        for row, name in enumerate((
            'Entry', 'FM252', 'Max Multiple', 'Outcome', 'Anchor', 'Sessions', '2X Time', '5X Time', '10X Time'
        ), start=1):
            label = QLabel(name)
            label.setObjectName('Muted')
            value = QLabel('—')
            backtest.addWidget(label, row, 0)
            backtest.addWidget(value, row, 1)
            self.backtest_values[name] = value
        layout.addWidget(self.backtest_card, 1)

        self.forecast_card = QFrame()
        self.forecast_card.setObjectName('Card')
        forecast = QGridLayout(self.forecast_card)
        self.forecast_status = QLabel('NOT AVAILABLE')
        self.forecast_status.setObjectName('Muted')
        self.forecast_values = {}
        forecast.addWidget(QLabel('12M Forward Forecast'), 0, 0)
        forecast.addWidget(self.forecast_status, 0, 1)
        for row, name in enumerate((
            'Bull', 'Base', 'Bear', 'Positive', '2X+', '5X+', '10X+', 'Confidence', 'Risk', 'Calibration'
        ), start=1):
            label = QLabel(name)
            label.setObjectName('Muted')
            value = QLabel('—')
            forecast.addWidget(label, row, 0)
            forecast.addWidget(value, row, 1)
            self.forecast_values[name] = value
        layout.addWidget(self.forecast_card, 1)

    def set_backtest(self, view: BacktestView) -> None:
        self.backtest_status.setText(view.status)
        values = {
            'Entry': '—' if view.entry_price is None else f'${view.entry_price:,.2f}',
            'FM252': _num(view.fm252, 'x', 2),
            'Max Multiple': _num(view.max_multiple_observed, 'x', 2),
            'Outcome': view.outcome_class or '—',
            'Anchor': view.anchor_session or '—',
            'Sessions': '—' if view.horizon_sessions_available is None else str(view.horizon_sessions_available),
            '2X Time': '—' if view.time_to_2x_sessions is None else f'{view.time_to_2x_sessions} sessions',
            '5X Time': '—' if view.time_to_5x_sessions is None else f'{view.time_to_5x_sessions} sessions',
            '10X Time': '—' if view.time_to_10x_sessions is None else f'{view.time_to_10x_sessions} sessions',
        }
        for name, value in values.items():
            self.backtest_values[name].setText(value)

    def set_forecast(self, view: ForecastView) -> None:
        self.forecast_status.setText(view.status)
        values = {
            'Bull': _num(view.bull_return_pct, '%'),
            'Base': _num(view.base_return_pct, '%'),
            'Bear': _num(view.bear_return_pct, '%'),
            'Positive': _num(view.probability_positive_return_pct, '%'),
            '2X+': _num(view.probability_2x_plus_pct, '%'),
            '5X+': _num(view.probability_5x_plus_pct, '%'),
            '10X+': _num(view.probability_10x_plus_pct, '%'),
            'Confidence': _num(view.confidence_pct, '%'),
            'Risk': view.risk or '—',
            'Calibration': view.calibration_id or '—',
        }
        for name, value in values.items():
            self.forecast_values[name].setText(value)
