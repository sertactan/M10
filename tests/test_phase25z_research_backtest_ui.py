"""Synthetic Qt checks for research/canonical separation; no private files opened."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.ui.main_window import ResearchTerminalWindow
from app.ui.research_backtest_page import REQUIRED_RISKS, read_research_report


class ResearchBacktestUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "research.json"
        names = [f"T{i:02d}" for i in range(25)]
        self.report = {
            "schema": "phase25z_research_backtest_v2", "status": "EXPERIMENTAL_RESEARCH_ONLY",
            "pilot_size": 25, "cohort_tickers": names,
            "period": {"start": "2024-01-01", "end": "2025-09-30"},
            "canonical_accepted_securities": 0, "canonical_accepted_security_dates": 0,
            "wf9_status": "BLOCKED", "learning_v3_status": "NOT_TRAINED",
            "research_mode": "ENABLED_EXPERIMENTAL_ONLY",
            "canonical_mode": "BLOCKED_MISSING_ALL_REQUIRED_EVIDENCE",
            "source_price_sha256": "a" * 64, "input_sha256": {"phase25w.json": "b" * 64},
            "risk_ledger": [{"code": code, "level": "BLOCKED", "detail": "synthetic limit"} for code in REQUIRED_RISKS],
            "diagnostics": {
                "source_adj_index_final": 1.2, "source_close_index_final": 1.1,
                "monthly_diagnostics": [{"to": f"{2024 + (m + 1) // 13}-{((m + 1 - 1) % 12) + 1:02d}",
                                         "source_adj_index": 1.0 + m / 100,
                                         "source_close_index": 1.0 + m / 200} for m in range(1, 21)],
                "exact_rebalanced_source_adj_index_contribution": {t: 0.008 for t in names},
                "leave_one_out": {t: {"index_without": 1.0} for t in names},
                "largest_single_name_month_moves": [{"ticker": "T00", "from": "2024-01",
                                                     "to": "2024-02", "source_adj_return": 0.2}],
            },
        }
        self.write_report()

    def tearDown(self):
        self.temp.cleanup()

    def write_report(self):
        self.path.write_text(json.dumps(self.report), encoding="utf-8")

    def test_private_report_view_shows_research_and_canonical_separately(self):
        window = ResearchTerminalWindow(research_backtest_report_path=self.path)
        window.show()
        window.tabs.setCurrentWidget(window.research_backtest_page)
        self.app.processEvents()
        page = window.research_backtest_page
        self.assertIn("CANONICAL: 0", page.summary.text())
        self.assertIn("NOT_TRAINED", page.summary.text())
        self.assertEqual(page.contributions.rowCount(), 25)
        self.assertEqual(len(page.chart.series()), 2)
        self.assertFalse(window.context_panel.isVisible())
        window.tabs.setCurrentIndex(0)
        self.app.processEvents()
        self.assertTrue(window.context_panel.isVisible())
        window.close()

    def test_window_constructs_when_windows_localappdata_is_absent(self):
        with patch.dict(os.environ, {"LOCALAPPDATA": ""}):
            window = ResearchTerminalWindow()
            self.assertIn("phase25z", str(window.research_backtest_page.report_path))
            window.close()

    def test_canonical_promotion_in_report_is_rejected(self):
        self.report["canonical_accepted_securities"] = 1
        self.write_report()
        with self.assertRaisesRegex(ValueError, "zero-canonical"):
            read_research_report(self.path)

    def test_missing_monthly_close_path_is_rejected(self):
        del self.report["diagnostics"]["monthly_diagnostics"][0]["source_close_index"]
        self.write_report()
        with self.assertRaisesRegex(ValueError, "Incomplete V2"):
            read_research_report(self.path)


if __name__ == "__main__":
    unittest.main()
