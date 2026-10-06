from __future__ import annotations

from datetime import date
from typing import Callable

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class AnalysisSignals(QObject):
    completed = Signal(object)
    failed = Signal(str)


class AnalysisTask(QRunnable):
    def __init__(
        self,
        service_factory: Callable[[], object],
        *,
        ticker: str,
        as_of_date: date,
    ) -> None:
        super().__init__()
        self.service_factory = service_factory
        self.ticker = ticker
        self.as_of_date = as_of_date
        self.signals = AnalysisSignals()

    @Slot()
    def run(self) -> None:
        try:
            service = self.service_factory()
            result = service.analyze(ticker=self.ticker, as_of_date=self.as_of_date)
        except Exception as exc:
            self.signals.failed.emit(str(exc))
            return
        self.signals.completed.emit(result)
