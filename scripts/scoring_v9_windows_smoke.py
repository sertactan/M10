"""Windows Qt V9 full-Research acceptance smoke on the private 17-score report."""
from pathlib import Path
import argparse,json,os,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from app.ui.main_window import ResearchTerminalWindow

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--report',type=Path,required=True)
p.add_argument('--phase27',type=Path,required=True)
p.add_argument('--phase28',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args()
if a.out.exists():raise ValueError('V9_NEW_PRIVATE_SMOKE_OUTPUT_REQUIRED')
if 'E:/M10/.scoring_v9_private' not in a.out.resolve().as_posix():
    raise ValueError('V9_STAGING_RECEIPT_PRIVATE_ONLY')
a.out.mkdir(parents=True)
os.environ['QT_QPA_PLATFORM']='offscreen'
os.environ['M10_PHASE27_STAGING_DB']=str(a.phase27)
os.environ['M10_PHASE28_STAGING_DB']=str(a.phase28)
os.environ['M10_SCORING_COMPLETION_REPORT']=str(a.report)
app=QApplication([])
window=ResearchTerminalWindow();window.show()
result={}

def check():
    try:
        page=window.scoring_completion_page
        page.refresh()
        assert page.report is not None
        assert page.comparison.rowCount()==5
        assert page.comparison.columnCount()==15
        assert page.report['full_model_count']==17
        stocks={s['ticker']:s for s in page.report['stocks']}
        expected={'INOD':500/9,'CRMD':500/9,'TMDX':700/9,'PENG':600/9,'ETON':500/9}
        for ticker,score in expected.items():
            model=next(m for m in stocks[ticker]['models'] if m['model']=='S9')
            assert model['score'] is not None and abs(model['score']-score)<1e-11
            assert model['status']=='REAL_SCORE_ACCEPTED_RESEARCH'
        for ticker in ('INOD','CRMD'):
            model=next(m for m in stocks[ticker]['models'] if m['model']=='S9')
            assert model['canonical_accepted'] is False
            assert model['historical_pit_accepted'] is False
        assert stocks['INOD']['quality']['S11']['score']==0.0
        assert all(next(m for m in s['models'] if m['model']=='S14')['score'] is None
                   for s in stocks.values())
        assert page.report['v9']['s16_c_pit_features']==0
        assert page.report['canonical_securities']==0
        for i in range(5):
            page.comparison.selectRow(i);app.processEvents()
            assert page.models.rowCount()==20
        window.tabs.setCurrentWidget(page);app.processEvents()
        assert window.grab().save(str(a.out/'window.png'))
        result.update(status='PASS',stocks=5,columns=15,
            research_full_scores=17,new_complete_research=2,
            INOD_S9=expected['INOD'],CRMD_S9=expected['CRMD'],
            S11_INOD=0.0,S14=None,S16_C_accepted=0,canonical=0)
    except Exception as exc:
        result.update(status='FAIL',error=f'{type(exc).__name__}: {exc}')
    finally:
        window.close();app.quit()

QTimer.singleShot(750,check)
result['qt_exit']=app.exec()
result['window_closed']=not window.isVisible()
(a.out/'receipt.json').write_text(json.dumps(result,indent=2),encoding='utf8')
print(json.dumps(result,sort_keys=True))
raise SystemExit(0 if result.get('status')=='PASS' and result['window_closed'] else 1)
