from __future__ import annotations

import os
import uuid
from datetime import date, datetime, timedelta, timezone

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from app.ui.data_health_dialog import DataHealthDialog
from app.ui.data_health_service import DataHealthService
from app.ui.main_window import ResearchTerminalWindow
from data.database.sqlite_store import SQLiteStore
from data.repositories.background_sync_repository import BackgroundSyncRepository
from data.repositories.provider_health_repository import ProviderHealthRepository


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _seed_health_store(tmp_path):
    store = SQLiteStore(tmp_path / "health.sqlite")
    store.initialize()
    now = datetime.now(timezone.utc)

    store.connection.execute(
        """
        INSERT INTO security_master (
            security_id,ticker,name,exchange,market,active,created_at,updated_at
        ) VALUES (?,?,?,?,?,?,?,?)
        """,
        (
            "SEC_TEST",
            "TEST",
            "Test Inc.",
            "NASDAQ",
            "US",
            1,
            now.isoformat(),
            now.isoformat(),
        ),
    )
    store.connection.execute(
        """
        INSERT INTO canonical_price_selection (
            selection_id,security_id,purpose,start_date,end_date,
            source,source_symbol,reason,selected_at
        ) VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (
            str(uuid.uuid4()),
            "SEC_TEST",
            "BACKTEST_ADJUSTED",
            (now.date() - timedelta(days=365)).isoformat(),
            (now.date() - timedelta(days=10)).isoformat(),
            "SIMFIN",
            "TEST",
            "observability-test",
            now.isoformat(),
        ),
    )
    store.connection.commit()

    health = ProviderHealthRepository(store)
    health.record_success("SEC_EDGAR", latency_ms=120.0)
    health.record_failure(
        "SEC_EDGAR",
        latency_ms=800.0,
        rate_limited=True,
        message="429 rate limit",
    )

    BackgroundSyncRepository(store).enqueue(
        "PRICE",
        "price:TEST:observability",
        {"ticker": "TEST", "as_of": now.date().isoformat()},
    )
    return store


def test_data_health_service_surfaces_provider_cache_and_queue(tmp_path):
    store = _seed_health_store(tmp_path)
    try:
        snapshot = DataHealthService(store=store).snapshot()
        sec = next(row for row in snapshot.providers if row.provider == "SEC_EDGAR")

        assert sec.circuit_state == "CLOSED"
        assert sec.availability_pct == pytest.approx(50.0)
        assert sec.error_rate_pct == pytest.approx(50.0)
        assert sec.rate_limit_status.startswith("THROTTLED")
        assert sec.last_message == "429 rate limit"
        assert sec.last_success_at is not None

        assert snapshot.cache.status == "LAST_KNOWN_GOOD"
        assert snapshot.cache.source == "SIMFIN"
        assert snapshot.cache.age_days == 10

        assert snapshot.background_sync.status == "QUEUED"
        assert snapshot.background_sync.queue_depth == 1
        assert snapshot.background_sync.pending == 1
        assert snapshot.background_sync.last_task_type == "PRICE"
    finally:
        store.close()


def test_data_health_dialog_renders_diagnostics(qapp, tmp_path):
    store = _seed_health_store(tmp_path)
    dialog = DataHealthDialog(
        service_factory=lambda: DataHealthService(store=store),
        auto_refresh_ms=60000,
    )
    try:
        assert dialog.table.rowCount() >= 8
        assert "LAST_KNOWN_GOOD" in dialog.cache_status.text()
        assert "queue 1" in dialog.sync_status.text()
        provider_names = {
            dialog.table.item(row, 0).text()
            for row in range(dialog.table.rowCount())
        }
        assert "SEC_EDGAR" in provider_names
        assert "diagnostics loaded" in dialog.status.text()
    finally:
        dialog.timer.stop()
        dialog.close()
        store.close()


def test_main_window_exposes_data_health_button_and_fails_closed_without_backend(qapp):
    window = ResearchTerminalWindow()
    try:
        assert window.data_health_button.text() == "DATA HEALTH"
        window.data_health_button.click()
        assert window.status.text() == "Data health backend is not connected"
    finally:
        window.close()
