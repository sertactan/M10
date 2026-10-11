"""Source Windows staging smoke; no bootstrap, provider calls, production DB or installs."""
from pathlib import Path
import sys,os,json,argparse
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from app.ui.main_window import ResearchTerminalWindow
p=argparse.ArgumentParser();p.add_argument('--report',type=Path,required=True);p.add_argument('--phase27',type=Path,required=True);p.add_argument('--phase28',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
p.add_argument('--v4-rsst-receipt',type=Path);p.add_argument('--v4-companyfacts-zip',type=Path)
p.add_argument('--v4-model-source',type=Path);p.add_argument('--v4-filing-cache',type=Path);a=p.parse_args()
if a.out.exists():raise ValueError('New private smoke output required')
a.out.mkdir(parents=True)
os.environ['M10_PHASE27_STAGING_DB']=str(a.phase27);os.environ['M10_PHASE28_STAGING_DB']=str(a.phase28);os.environ['M10_SCORING_COMPLETION_REPORT']=str(a.report)
if a.v4_rsst_receipt:
 if not all((a.v4_companyfacts_zip,a.v4_model_source,a.v4_filing_cache)):
  raise ValueError('V4 source replay paths required')
 os.environ['M10_SCORING_V4_RSST_RECEIPT']=str(a.v4_rsst_receipt)
 os.environ['M10_SCORING_V4_COMPANYFACTS_ZIP']=str(a.v4_companyfacts_zip)
 os.environ['M10_SCORING_V4_MODEL_SOURCE']=str(a.v4_model_source)
 os.environ['M10_SCORING_V4_FILING_CACHE']=str(a.v4_filing_cache)
app=QApplication([]);window=ResearchTerminalWindow();window.show()
result={}
def check():
 try:
  page=window.scoring_completion_page;page.refresh();assert page.report is not None
  assert page.comparison.rowCount()==5 and page.comparison.columnCount()==14
  assert page.report['full_model_count']==10
  inod=page.report['stocks'][0]
  assert inod['ticker']=='INOD' and inod['quality']['S11']['score']==0.0
  assert inod['task9_financial_evidence']['S6_verified_count']==5
  if a.v4_rsst_receipt:
   assert page.v4_rsst['RSST_decimal']=='0.05914012806603271853128257494'
   assert page.v4_rsst['RSST_frozen_accepted'] is False
   assert 'RSST' in page.comparison.item(0,9).text()
  assert next(m for m in inod['models'] if m['model']=='S14')['score'] is None
  for i in range(5):
   page.comparison.selectRow(i);app.processEvents();assert page.models.rowCount()==20
  page.comparison.selectRow(0)
  labels=[window.tabs.tabText(i) for i in range(window.tabs.count())]
  for i in range(window.tabs.count()):window.tabs.setCurrentIndex(i);app.processEvents()
  window.tabs.setCurrentWidget(page);app.processEvents()
  assert window.grab().save(str(a.out/'window.png'))
  result.update(status='PASS',platform=app.platformName(),tabs=labels,stocks=5,research_full_scores=10,
                S11_INOD=0.0,S14_INOD=None,S6_frozen_accepted_inputs=5,
                S6_RSST_research_candidate=page.v4_rsst['RSST_decimal'] if page.v4_rsst else None,
                canonical=0,
                production_services_configured=False)
 except Exception as exc:result.update(status='FAIL',error=f'{type(exc).__name__}: {exc}')
 finally:
  window.close();app.quit()
QTimer.singleShot(700,check)
code=app.exec();result['qt_exit']=code;result['window_closed']=not window.isVisible()
(a.out/'receipt.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result))
raise SystemExit(0 if result.get('status')=='PASS' and result['window_closed'] else 1)
