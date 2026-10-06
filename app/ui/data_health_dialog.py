from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)


class DataHealthDialog(QDialog):
    def __init__(
        self,
        *,
        service_factory: Callable[[], object] | None,
        parent=None,
        auto_refresh_ms: int = 5000,
    ) -> None:
        super().__init__(parent)
        self.service_factory = service_factory
        self.setWindowTitle("Data Health")
        self.resize(1260, 700)
        self.setMinimumSize(980, 560)

        root = QVBoxLayout(self)
        top = QHBoxLayout()
        self.summary = QLabel("DATA HEALTH — not loaded")
        self.summary.setObjectName("AppTitle")
        top.addWidget(self.summary, 1)
        self.refresh_button = QPushButton("REFRESH")
        self.refresh_button.clicked.connect(self.refresh)
        top.addWidget(self.refresh_button)
        root.addLayout(top)

        self.cache_status = QLabel("Cache: —")
        self.cache_status.setObjectName("Muted")
        root.addWidget(self.cache_status)
        self.sync_status = QLabel("Background sync: —")
        self.sync_status.setObjectName("Muted")
        root.addWidget(self.sync_status)

        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels(
            [
                "Provider",
                "Health",
                "Circuit",
                "Availability",
                "Error",
                "Latency",
                "Freshness",
                "Rate Limit",
                "Last Success",
                "Last Error",
            ]
        )
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.table, 1)

        self.status = QLabel("READY")
        self.status.setObjectName("Muted")
        root.addWidget(self.status)

        self.timer = QTimer(self)
        self.timer.setInterval(max(1000, int(auto_refresh_ms)))
        self.timer.timeout.connect(self.refresh)
        if self.service_factory is not None:
            self.timer.start()
            self.refresh()

    @staticmethod
    def _age_text(seconds: float | None) -> str:
        if seconds is None:
            return "NEVER"
        if seconds < 60:
            return f"{int(seconds)}s"
        if seconds < 3600:
            return f"{int(seconds // 60)}m"
        if seconds < 86400:
            return f"{seconds / 3600:.1f}h"
        return f"{seconds / 86400:.1f}d"

    @staticmethod
    def _time_text(value: datetime | None) -> str:
        if value is None:
            return "—"
        return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    def refresh(self) -> None:
        if self.service_factory is None:
            self.status.setText("Data health backend is not connected")
            return
        try:
            snapshot = self.service_factory().snapshot()
        except Exception as exc:
            self.status.setText(f"ERROR — {exc}")
            return
        self.apply_snapshot(snapshot)

    def apply_snapshot(self, snapshot) -> None:
        self.summary.setText(
            f"DATA HEALTH — {snapshot.observed_at.astimezone(timezone.utc).strftime('%H:%M:%S UTC')}"
        )

        cache = snapshot.cache
        if cache.status == "EMPTY":
            self.cache_status.setText("Cache: EMPTY — no canonical price selection")
        else:
            self.cache_status.setText(
                "Cache: "
                f"{cache.status} · {cache.source}:{cache.source_symbol} · "
                f"end {cache.end_date} · age {cache.age_days}d"
            )

        sync = snapshot.background_sync
        self.sync_status.setText(
            "Background sync: "
            f"{sync.status} · queue {sync.queue_depth} · "
            f"pending {sync.pending} · running {sync.running} · "
            f"retry {sync.retry} · failed {sync.failed}"
        )

        self.table.setRowCount(len(snapshot.providers))
        for row_index, provider in enumerate(snapshot.providers):
            values = [
                provider.provider,
                f"{provider.health_score:.1f}",
                provider.circuit_state,
                f"{provider.availability_pct:.1f}%",
                f"{provider.error_rate_pct:.1f}%",
                f"{provider.latency_ms:.0f} ms" if provider.latency_ms is not None else "—",
                self._age_text(provider.freshness_age_seconds),
                provider.rate_limit_status,
                self._time_text(provider.last_success_at),
                provider.last_message or "—",
            ]
            for col, value in enumerate(values):
                self.table.setItem(row_index, col, QTableWidgetItem(str(value)))

        self.table.resizeColumnsToContents()
        self.status.setText(
            "OK — provider, cache and background-sync diagnostics loaded"
        )
