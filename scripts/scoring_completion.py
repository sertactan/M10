from pathlib import Path
import argparse
import sys
import json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.scoring_completion import (build_report,save_report,attach_intraday,
                                    attach_sec_companyfacts_partial,attach_v3_financial_quality)
p=argparse.ArgumentParser(description='Offline five-stock scoring evidence completion')
p.add_argument('--phase27',type=Path,required=True)
p.add_argument('--phase28',type=Path,required=True)
p.add_argument('--intraday-receipt',type=Path)
p.add_argument('--sec-submissions',type=Path)
p.add_argument('--sec-quality-receipt',type=Path)
p.add_argument('--v3-sec-quality-receipt',type=Path)
p.add_argument('--v3-companyfacts',type=Path)
p.add_argument('--v3-submissions',type=Path)
p.add_argument('--v3-10k-body',type=Path)
p.add_argument('--v3-forensic-receipt',type=Path)
p.add_argument('--v3-filing-cache',type=Path)
p.add_argument('--v3-jones-receipt',type=Path)
p.add_argument('--task9-financial-receipt',type=Path)
p.add_argument('--task9-forensic-receipt',type=Path)
p.add_argument('--task9-forensic-v3-report',type=Path)
p.add_argument('--task9-s13-contract',type=Path)
p.add_argument('--task9-jones-receipt',type=Path)
p.add_argument('--task9-jones-cache',type=Path)
p.add_argument('--archive',type=Path)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
r=build_report(a.phase27,a.phase28,a.archive,a.sec_submissions)
if a.intraday_receipt:r=attach_intraday(r,a.intraday_receipt)
if a.sec_quality_receipt:r=attach_sec_companyfacts_partial(r,a.sec_quality_receipt)
if a.v3_sec_quality_receipt:
    if not a.v3_companyfacts or not a.v3_submissions:
        raise ValueError('V3 receipt requires both original SEC cached files')
    r=attach_v3_financial_quality(r,a.v3_sec_quality_receipt,a.v3_companyfacts,
                                   a.v3_submissions,a.v3_10k_body)
if a.v3_forensic_receipt:
    if not a.v3_submissions or not a.v3_filing_cache:
        raise ValueError('Forensic receipt requires original SEC submissions and private body cache')
    from app.scoring_completion import attach_v3_sec_forensic_candidates
    r=attach_v3_sec_forensic_candidates(r,a.v3_forensic_receipt,
                                        a.v3_submissions,a.v3_filing_cache)
if a.v3_jones_receipt:
    if not a.v3_submissions or not a.v3_companyfacts:
        raise ValueError('Jones research audit requires SEC raw source files')
    from app.scoring_completion import attach_v3_jones_peer_audit
    r=attach_v3_jones_peer_audit(r,a.v3_jones_receipt,a.v3_companyfacts,a.v3_submissions)
if a.task9_financial_receipt:
    if not a.v3_companyfacts or not a.v3_submissions or not a.v3_filing_cache:
        raise ValueError('Task9 original SEC Companyfacts, Submissions and 10-K bodies required')
    from app.scoring_completion import attach_task9_issuance_evidence
    r=attach_task9_issuance_evidence(r,a.task9_financial_receipt,
                                     a.v3_companyfacts,a.v3_submissions,a.v3_filing_cache)
if a.task9_forensic_receipt:
    if not all((a.v3_filing_cache,a.task9_forensic_v3_report,a.task9_s13_contract)):
        raise ValueError('Task9 S13 review requires full 14 SEC filing, V3 receipt and original frozen contract')
    from app.scoring_completion import attach_task9_forensic_context
    r=attach_task9_forensic_context(r,a.task9_forensic_receipt,
                                     a.v3_filing_cache,a.task9_forensic_v3_report,
                                     a.task9_s13_contract)
if a.task9_jones_receipt:
    if not a.task9_jones_cache:
        raise ValueError('Independent Task9 Jones original SEC response cache is required')
    from app.scoring_completion import attach_task9_jones_real_score
    r=attach_task9_jones_real_score(r,a.task9_jones_receipt,a.task9_jones_cache)
save_report(r,a.output)
print(json.dumps({'full_model_count':r['full_model_count'],'stocks':[{'ticker':s['ticker'],'features':len(s['features']),'new':len(s['new_feature_keys']),'core_inputs':s['control_chain']['discovery_inputs_present'],'price':s['price'],'price_time':s['price_time'],'period':s['financial_period'],'s16_raw':sum(bool(f['raw']) for f in s['s16_features'])} for s in r['stocks']]},indent=2))
