"""Offscreen Windows staging check for the sealed V6 five-stock report."""
from pathlib import Path
import argparse
import json
import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from app.ui.main_window import ResearchTerminalWindow

p = argparse.ArgumentParser()
p.add_argument('--report', type=Path, required=True)
p.add_argument('--phase27', type=Path, required=True)
p.add_argument('--phase28', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
if a.out.exists():
    raise ValueError('New private smoke output required')
a.out.mkdir(parents=True)
os.environ['M10_PHASE27_STAGING_DB'] = str(a.phase27)
os.environ['M10_PHASE28_STAGING_DB'] = str(a.phase28)
os.environ['M10_SCORING_COMPLETION_REPORT'] = str(a.report)
app = QApplication([])
window = ResearchTerminalWindow()
window.show()
result = {}

def check():
    try:
        page = window.scoring_completion_page
        page.refresh()
        assert page.report is not None
        assert page.comparison.rowCount() == 5
        assert page.comparison.columnCount() == 14
        assert page.report['full_model_count'] == 12
        stocks = {s['ticker']: s for s in page.report['stocks']}
        assert stocks['INOD']['quality']['S11']['score'] == 0.0
        assert abs(stocks['ETON']['quality']['S11']['score'] - 7.860332129752234) < 1e-10
        assert abs(stocks['CRMD']['quality']['S11']['score'] - 86.01535933860907) < 1e-10
        assert stocks['INOD']['task9_financial_evidence']['S6_verified_count'] == 5
        for s in stocks.values():
            assert next(m for m in s['models'] if m['model'] == 'S14')['score'] is None
        for i in range(5):
            page.comparison.selectRow(i)
            app.processEvents()
            assert page.models.rowCount() == 20
        window.tabs.setCurrentWidget(page)
        app.processEvents()
        assert window.grab().save(str(a.out/'window.png'))
        result.update(status='PASS', stocks=5, columns=14,
                      research_full_scores=12, S11_INOD=0.0,
                      S11_ETON=stocks['ETON']['quality']['S11']['score'],
                      S11_CRMD=stocks['CRMD']['quality']['S11']['score'],
                      S14_INOD=None, canonical=0)
    except Exception as exc:
        result.update(status='FAIL', error=f'{type(exc).__name__}: {exc}')
    finally:
        window.close()
        app.quit()

QTimer.singleShot(700, check)
result['qt_exit'] = app.exec()
result['window_closed'] = not window.isVisible()
(a.out/'receipt.json').write_text(json.dumps(result, indent=2), encoding='utf8')
print(json.dumps(result))
raise SystemExit(0 if result.get('status') == 'PASS' and result['window_closed'] else 1)
