from __future__ import annotations

import os
from datetime import datetime, timezone

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from app.ui.analysis_service import DesktopAnalysisView
from app.ui.main_window import ResearchTerminalWindow
from app.ui.theme import APP_QSS
from app.ui.view_models import ModelView


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_phase9_shell_has_required_global_header_and_tabs(qapp):
    window = ResearchTerminalWindow()
    try:
        assert window.windowTitle() == "S15.3 Research Terminal"
        assert window.market.count() == 1
        assert window.market.currentText() == "United States"
        assert window.horizon.currentData() == 12
        assert window.tabs.count() == 3
        assert [window.tabs.tabText(i) for i in range(3)] == [
            "V1.2", "V1.4", "COMPARE"
        ]
        assert window.v12_page.score.text() == "—"
        assert window.v12_page.status.text() == "NOT LOADED"
        assert window.v14_page.score.text() == "—"
        assert window.v14_page.status.text() == "NOT LOADED"
        assert "background: #0B1220" in APP_QSS
    finally:
        window.close()


def test_phase9_empty_ticker_does_not_dispatch_analysis(qapp):
    window = ResearchTerminalWindow()
    emitted = []
    window.analysis_requested.connect(lambda ticker, as_of: emitted.append((ticker, as_of)))
    try:
        window.ticker.setText("")
        window.run_button.click()
        assert emitted == []
        assert window.status.text() == "Ticker is required"
    finally:
        window.close()


def test_phase9_normalizes_ticker_and_emits_request(qapp):
    window = ResearchTerminalWindow()
    emitted = []
    window.analysis_requested.connect(lambda ticker, as_of: emitted.append((ticker, as_of)))
    try:
        window.ticker.setText("crmd")
        window.run_button.click()
        assert emitted
        assert emitted[0][0] == "CRMD"
        assert window.status.text() == "Analysis backend is not connected"
    finally:
        window.close()


def test_phase9_applies_real_result_surface_without_synthetic_consensus(qapp):
    window = ResearchTerminalWindow()
    result = DesktopAnalysisView(
        ticker="TEST",
        as_of=datetime(2026, 10, 6, tzinfo=timezone.utc),
        v12=ModelView(
            model_name="S15.3 V1.2",
            status="READY",
            score=81.2,
            route="F10",
            destination=None,
            confidence=78.0,
            risk=None,
        ),
        v14=ModelView(
            model_name="S15.3 V1.4",
            status="BLOCKED_CANONICAL_SPEC",
        ),
        v12_components={"Core15.3": 81.2},
        v14_components={},
    )
    try:
        window._apply_analysis(result)
        assert window.v12_page.score.text() == "81.2 / 100"
        assert window.v12_page.route.text() == "F10"
        assert window.v14_page.status.text() == "BLOCKED_CANONICAL_SPEC"
        assert window.compare_page.consensus.text() == "MODEL CONSENSUS: —"
        assert window.compare_page.winner.text() == "Winner: —"
        assert "LOADED TEST" in window.status.text()
    finally:
        window.close()
