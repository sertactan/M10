"""Offscreen Windows staging check for the sealed V7 five-stock report."""
from pathlib import Path
import argparse, json, os, sys

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
        assert page.comparison.columnCount() == 15
        assert page.report['full_model_count'] == 15
        stocks = {s['ticker']: s for s in page.report['stocks']}
        expected = {'TMDX': 700/9, 'PENG': 600/9, 'ETON': 500/9}
        for ticker, score in expected.items():
            s9 = next(m for m in stocks[ticker]['models'] if m['model'] == 'S9')
            assert abs(s9['score'] - score) < 1e-10
            assert s9['status'] == 'REAL_SCORE_ACCEPTED_RESEARCH'
        assert next(m for m in stocks['INOD']['models'] if m['model'] == 'S9')['score'] is None
        assert next(m for m in stocks['CRMD']['models'] if m['model'] == 'S9')['score'] is None
        assert stocks['INOD']['quality']['S11']['score'] == 0.0
        assert next(m for m in stocks['INOD']['models'] if m['model'] == 'S14')['score'] is None
        for i in range(5):
            page.comparison.selectRow(i)
            app.processEvents()
            assert page.models.rowCount() == 20
        for i, ticker in enumerate(s['ticker'] for s in page.report['stocks']):
            if ticker in expected:
                assert page.comparison.item(i, 6).text() != 'N/A'
        window.tabs.setCurrentWidget(page)
        app.processEvents()
        assert window.grab().save(str(a.out/'window.png'))
        result.update(status='PASS', stocks=5, columns=15, research_full_scores=15,
                      S9=expected, S11_INOD=0.0, S14_INOD=None, canonical=0)
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
