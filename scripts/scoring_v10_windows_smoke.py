"""Read-only V10 staging check of all 17 preserved V9 source scores."""
from __future__ import annotations
import json,os,sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from app.ui.scoring_completion_page import ScoringCompletionPage

OUTPUT=Path('E:/M10/.scoring_v10_private/windows_smoke/v10_baseline17.json')
SOURCE=Path('E:/M10/.scoring_v9_private/scoring_completion/v9_research_report.json')
rt=Path(os.environ['LOCALAPPDATA'])/'S153ResearchTerminal/runtime'
os.environ['QT_QPA_PLATFORM']='offscreen'
app=QApplication([])
page=ScoringCompletionPage(SOURCE, rt/'phase27/current_scoring/staging.db',rt/'phase28/real_scoring_v1/stage.db')
result={'checkpoint':'V9_17_RESEARCH_BASELINE_V10_ISOLATED_QT_SMOKE','status':'FAIL',
        'canonical_accepted':None, 'windows_staging_not_production':True}

def validate():
    try:
        page.show();page.refresh()
        assert page.report is not None
        assert page.comparison.rowCount()==5
        assert page.comparison.columnCount()==15
        assert page.report['full_model_count']==17
        assert page.report['canonical_securities']==0
        assert page.report['v9']['s16_c_pit_features']==0
        expected={'INOD':500/9,'TMDX':700/9,'CRMD':500/9,'PENG':600/9,'ETON':500/9}
        for row in page.report['stocks']:
            t=row['ticker']; models={m['model']:m for m in row['models']}
            assert abs(models['S9']['score']-expected[t])<1e-11
            assert models['S14']['score'] is None
            assert models['S8']['score'] is None and models['S10']['score'] is None
            assert models['S16']['score'] is None if 'S16' in models else True
        assert next(s for s in page.report['stocks'] if s['ticker']=='INOD')['quality']['S11']['score']==0
        result.update(status='PASS',stocks=5,columns=15,full_research_scores=17,
                      new_V10_model_scores=0, canonical_accepted=0,S16_C_PIT_features=0)
    except Exception as exc:
        result.update(error=f'{type(exc).__name__}: {exc}')
    finally:
        page.close();app.quit()

QTimer.singleShot(100,validate)
result['qt_exit']=app.exec();result['window_closed']=not page.isVisible()
OUTPUT.parent.mkdir(parents=True,exist_ok=True)
if OUTPUT.exists():
    if json.loads(OUTPUT.read_text(encoding='utf8'))!=result:
        raise ValueError('V10_STAGING_REPORT_CHANGED_NO_OVERWRITE')
else:
    OUTPUT.write_text(json.dumps(result,indent=2,sort_keys=True),encoding='utf8')
print(json.dumps(result,sort_keys=True))
raise SystemExit(0 if result['status']=='PASS' and result['window_closed'] else 1)
