"""Offscreen Qt tests: real widget actions, five issuers, data and exports."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    from app.ui.personal_research_page import PersonalResearchPage
except ImportError:
    QApplication = None
    PersonalResearchPage = None

from tests.test_personal_research_core import baseline


@unittest.skipUnless(QApplication, "PySide6 not installed")
class PersonalUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root = Path(self.dir.name)
        baseline(self.root)
        self.page = PersonalResearchPage(
            evidence_root=self.root, sidecar=self.root / "runs.sqlite3")
        self.page.show()
        self.app.processEvents()
        self.addCleanup(self.page.close)

    def test_all_five_issuer_buttons_update_original_and_personal(self):
        for ticker in ("INOD", "CRMD", "ETON", "PENG", "TMDX"):
            self.page.ticker_combo.setCurrentText(ticker)
            self.page.run_button.click()
            self.app.processEvents()
            self.assertIsNotNone(self.page.report, ticker)
            self.assertEqual(self.page.report["ticker"], ticker)
            self.assertEqual(self.page.models_table.rowCount(), 4)
            self.assertEqual(self.page.s13_table.rowCount(), 7)
            self.assertTrue(self.page.export_button.isEnabled())
            self.assertEqual(self.page.report["baseline"]["score_count"], 17)
        self.page.close()
        self.page.show()
        self.app.processEvents()
        self.assertTrue(self.page.isVisible())

    def test_actual_export_and_source_error(self):
        self.page.run_button.click()
        with patch("app.ui.personal_research_page.QFileDialog.getSaveFileName",
                   return_value=(str(self.root / "myreport.json"), "JSON (*.json)")):
            self.page.export_button.click()
        self.assertTrue((self.root / "myreport.json").exists())
        self.assertTrue((self.root / "myreport.csv").exists())
        self.page.packet_path = str(self.root / "not-exist.json")
        self.page.run_button.click()
        self.assertIsNone(self.page.report)
        self.assertIn("HATA", self.page.status.text())


if __name__ == "__main__":
    unittest.main()
