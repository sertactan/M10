from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.ui.analysis_service import DesktopAnalysisService
from app.ui.main_window import ResearchTerminalWindow
from app.ui.theme import APP_QSS


def launch_ui(root: Path) -> int:
    application = QApplication.instance() or QApplication(sys.argv)
    application.setStyleSheet(APP_QSS)
    window = ResearchTerminalWindow(
        analysis_service_factory=lambda: DesktopAnalysisService(root)
    )
    window.show()
    return application.exec()
