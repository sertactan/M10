"""Seal new V9 17-score staging report and independently replay every source."""
from __future__ import annotations
import json,os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.scoring_v9_report import NEW_REPORT,create_report,load_v9_report

def main():
    rt=Path(os.environ['LOCALAPPDATA'])/'S153ResearchTerminal/runtime'
    phase27=rt/'phase27/current_scoring/staging.db'
    phase28=rt/'phase28/real_scoring_v1/stage.db'
    if NEW_REPORT.is_file():
        report=load_v9_report(NEW_REPORT,phase27,phase28)
    else:
        report=create_report(phase27,phase28)
        replay=load_v9_report(NEW_REPORT,phase27,phase28)
        if replay!=report:raise ValueError('NEW_PRIVATE_V9_REPORT_REPLAY_CHANGED')
    if report['full_model_count']!=17 or report['v9']['new_full_research_scores']!=2:
        raise ValueError('V9_TWO_NEW_S9_ACCEPTANCES_REQUIRED')
    print(json.dumps({'status':'V9_REAL_RESEARCH_ACCEPTED_OFFLINE_REPLAY',
        'total':17,'new':2,'INOD_S9':next(m['score'] for m in report['stocks'][0]['models'] if m['model']=='S9'),
        'CRMD_S9':next(m['score'] for m in report['stocks'][2]['models'] if m['model']=='S9'),
        'canonical':report['canonical_securities'],'S16_C_PIT_features':0,
        'private_report':str(NEW_REPORT)},sort_keys=True))
if __name__=='__main__': main()
