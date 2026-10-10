"""UI regressions use mocked reports; real Windows acceptance is separate."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from app.ui.scoring_completion_page import ScoringCompletionPage

class CompletionUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def test_failure_clears_cached_scores_and_details(self):
        page=ScoringCompletionPage(Path('missing'),Path('p27'),Path('p28'))
        page.comparison.setRowCount(5);page.models.setRowCount(20);page.details.setPlainText('stale')
        with patch('app.ui.scoring_completion_page.load_report',side_effect=ValueError('SOURCE_HASH_CHANGED')):
            page.refresh()
        self.assertEqual(page.comparison.rowCount(),0);self.assertEqual(page.models.rowCount(),0)
        self.assertEqual(page.details.toPlainText(),'');self.assertIn('SOURCE_HASH_CHANGED',page.status.text())
        page.close()
    def test_missing_report_never_constructs_placeholder_scores(self):
        page=ScoringCompletionPage(Path('no-such-completion.json'),Path('p27'),Path('p28'))
        page.refresh()
        self.assertIsNone(page.report);self.assertEqual(page.comparison.rowCount(),0)
        self.assertIn('MISSING',page.status.text());page.close()

if __name__=='__main__':unittest.main()
