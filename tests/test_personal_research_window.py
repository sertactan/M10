"""Regression: Personal tab is navigable inside the real desktop terminal."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PySide6.QtWidgets import QApplication
    from app.ui.main_window import ResearchTerminalWindow
except ImportError:
    QApplication = None
    ResearchTerminalWindow = None

from tests.test_personal_research_core import baseline


@unittest.skipUnless(QApplication, "PySide6 unavailable")
class WindowIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_tab_is_active_and_uses_actual_pipeline_and_can_grab(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline(root)
            with patch.dict(os.environ, {"M10_PERSONAL_EVIDENCE_ROOT": str(root),
                                         "M10_PERSONAL_SIDECAR": str(root / "sidecar.sqlite3")}):
                window = ResearchTerminalWindow()
                try:
                    self.assertIn("PERSONAL AI RESEARCH", [
                        window.tabs.tabText(i) for i in range(window.tabs.count())])
                    window.show()
                    window.tabs.setCurrentWidget(window.personal_research_page)
                    self.app.processEvents()
                    self.assertFalse(window.stock_header.isVisible())
                    window.personal_research_page.ticker_combo.setCurrentText("INOD")
                    window.personal_research_page.run_button.click()
                    self.app.processEvents()
                    self.assertEqual(window.personal_research_page.report["ticker"], "INOD")
                    self.assertEqual(window.personal_research_page.models_table.rowCount(), 4)
                    shot = root / "desktop_smoke.png"
                    self.assertTrue(window.grab().save(str(shot), "PNG"))
                    self.assertGreater(shot.stat().st_size, 1000)
                finally:
                    window.close()


if __name__ == "__main__":
    unittest.main()
