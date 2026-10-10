from pathlib import Path
import argparse
import sys
import json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.scoring_completion import build_report,save_report,attach_intraday
p=argparse.ArgumentParser(description='Offline five-stock scoring evidence completion')
p.add_argument('--phase27',type=Path,required=True)
p.add_argument('--phase28',type=Path,required=True)
p.add_argument('--intraday-receipt',type=Path)
p.add_argument('--sec-submissions',type=Path)
p.add_argument('--archive',type=Path)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
r=build_report(a.phase27,a.phase28,a.archive,a.sec_submissions)
if a.intraday_receipt:r=attach_intraday(r,a.intraday_receipt)
save_report(r,a.output)
print(json.dumps({'full_model_count':r['full_model_count'],'stocks':[{'ticker':s['ticker'],'features':len(s['features']),'new':len(s['new_feature_keys']),'core_inputs':s['control_chain']['discovery_inputs_present'],'price':s['price'],'price_time':s['price_time'],'period':s['financial_period'],'s16_raw':sum(bool(f['raw']) for f in s['s16_features'])} for s in r['stocks']]},indent=2))
