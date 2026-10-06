from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from app.background_sync import BackgroundSyncRuntime\nfrom app.ui.analysis_service import DesktopAnalysisService
from app.ui.main_window import ResearchTerminalWindow
from app.ui.scanner_service import DesktopScannerService
from app.ui.theme import APP_QSS
from core.runtime.errors import install_exception_handler
from core.runtime.logging import configure_logging
from core.runtime.settings import RuntimeSettings


def launch_ui(root: Path) -> int:
    configure_logging()
    application = QApplication.instance() or QApplication(sys.argv)
    application.setStyleSheet(APP_QSS)

    def notify_error(message: str) -> None:
        QMessageBox.critical(None, "S15.3 Research Terminal", message)

    install_exception_handler(user_notifier=notify_error)
    settings = RuntimeSettings()
    saved = settings.load()

    window = ResearchTerminalWindow(
        analysis_service_factory=lambda: DesktopAnalysisService(root),
        scanner_service_factory=lambda: DesktopScannerService(root),
    )
    width = int(saved.get("window_width", 1440))
    height = int(saved.get("window_height", 900))
    window.resize(max(width, 1100), max(height, 700))

    def persist_window_settings() -> None:
        settings.save(
            {
                "window_width": window.width(),
                "window_height": window.height(),
                "last_ticker": window.ticker.text().strip().upper(),
            }
        )

    last_ticker = str(saved.get("last_ticker") or "").strip().upper()
    if last_ticker:
        window.ticker.setText(last_ticker)

    background_sync = BackgroundSyncRuntime(root, warm_ticker=last_ticker or None)
    window.analysis_requested.connect(
        lambda ticker, _as_of: background_sync.request_ticker_warmup(ticker)
    )

    application.aboutToQuit.connect(persist_window_settings)
    application.aboutToQuit.connect(background_sync.stop)
    window.show()
    background_sync.start()
    return application.exec()
