"""Run real-source DEPI recovery and sealed INOD S6/B_Q/S13/S14 gate audit."""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path
import json, os, sys, zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.scoring_v10_quality import depreciation_component,inod_quality_gate,seal_private_report
from app.scoring_v9_s8_s10 import verify_frozen_source

PRIVATE=Path('E:/M10/.scoring_v10_private/quality')
OUTPUT=PRIVATE/'component_evidence_v2.json'

def sealed_load(path:Path)->dict:
    raw=path.read_bytes(); seal=Path(str(path)+'.sha256')
    if not seal.is_file() or seal.read_text('ascii').strip()!=sha256(raw).hexdigest():
        raise ValueError('HISTORICAL_PRIVATE_PROVENANCE_SEAL_CHANGED')
    return json.loads(raw)

def main():
    frozen_source_sha256=verify_frozen_source()
    rt=Path(os.environ['LOCALAPPDATA'])/'S153ResearchTerminal/runtime'
    zip_path=rt/'bulk/sec/companyfacts.zip'
    rows={}
    with zipfile.ZipFile(zip_path) as z:
        for ticker,cik in (('INOD','0000903651'),('CRMD','0001410098'),
                           ('ETON','0001710340'),('PENG','0001616533'),('TMDX','0001756262')):
            rows[ticker]=depreciation_component(ticker,z.read(f'CIK{cik}.json'))
    inod=sealed_load(Path('E:/M10/.scoring_v9_private/inod_s9/report.json'))
    expert=sealed_load(Path('E:/M10/.scoring_v5_private/s13/s13_expert_form_v5.json'))
    gates=inod_quality_gate(inod,expert)
    obj={'source_snapshot':'SEC_BULK_ORIGINAL_2026_10_11','year':'FY2025',
         'frozen_source_sha256':frozen_source_sha256,
         'research_only':True,'canonical_accepted':False,
         'components':rows,'INOD_quality_gates':gates,
         'S5_complete_scores':0,'B_Q_complete_scores':0,
         'S6_complete_scores':0,'S13_complete_scores':0,'S14_complete_scores':0,
         'v9_INOD_receipt_sha256':sha256(Path('E:/M10/.scoring_v9_private/inod_s9/report.json').read_bytes()).hexdigest(),
         'v5_S13_form_sha256':sha256(Path('E:/M10/.scoring_v5_private/s13/s13_expert_form_v5.json').read_bytes()).hexdigest()}
    digest=seal_private_report(OUTPUT,obj)
    print(json.dumps({'status':'REAL_COMPONENT_ONLY_NOT_FULL_MODEL',
        'pure_depreciation_components':{k:v['status'] for k,v in rows.items()},
        'S13_signed':gates['S13_signed_blocks'],'INOD_S14':gates['S14_score'],
        'private_receipt_sha256':digest},sort_keys=True))
if __name__=='__main__':main()
