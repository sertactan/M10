"""Offline-only Task9 accounting evidence; writes new private SHA-sealed JSON."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path

from app.task9_financial_recovery import recover_task9_evidence


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--companyfacts',type=Path,required=True)
    ap.add_argument('--submissions',type=Path,required=True)
    ap.add_argument('--filing-cache',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--as-of',default='2026-10-10T18:33:11+00:00')
    args=ap.parse_args()
    root=(Path(os.environ['LOCALAPPDATA'])/'S153ResearchTerminal'/'runtime'/'scoring_completion').resolve()
    output=args.output.resolve()
    if (output.parent.parent!=root or not output.parent.name.startswith('task9_')
        or output.name!='financial_recovery.json' or args.output.is_symlink()
        or output.exists() or Path(str(output)+'.sha256').exists()):
        raise ValueError('NEW_PRIVATE_TASK9_RESEARCH_REPORT_REQUIRED')
    filenames={2024:'000141057825000194_inod-20241231x10k.htm',
               2025:'000110465926020655_inod-20251231x10k.htm'}
    for src in (args.companyfacts,args.submissions,*[args.filing_cache/name for name in filenames.values()]):
        if not src.is_file() or src.is_symlink():
            raise ValueError('SOURCE_FILE_MISSING_OR_SYMLINK')
    facts=args.companyfacts.read_bytes()
    if sha256(facts).hexdigest()!='6ccc9dcc93b9c303cee51c166f345350fb16258408c884e2ed5d1231f2741b38':
        raise ValueError('FROZEN_SEC_COMPANYFACTS_SOURCE_CHANGED')
    bodies={y:(args.filing_cache/name).read_bytes() for y,name in filenames.items()}
    expected={2024:'a2c0241be84173898a65f43480a16346704f6d61786e3ab4feff61886d973031',
              2025:'2d5dd7f964d0239ea18a982f24e077d1b8e0f08baa73fd28dd66f539d9befba2'}
    if any(sha256(bodies[y]).hexdigest()!=expected[y] for y in bodies):
        raise ValueError('ORIGINAL_10K_BYTES_CHANGED')
    result=recover_task9_evidence(facts,args.submissions.read_bytes(),bodies,retrieved_at=args.as_of)
    output.parent.mkdir(parents=True,exist_ok=True)
    raw=json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True,allow_nan=False).encode('utf8')
    with output.open('xb') as f: f.write(raw)
    seal=sha256(raw).hexdigest()
    with Path(str(output)+'.sha256').open('x',encoding='ascii') as f: f.write(seal+'\n')
    print(json.dumps({
      'ISSUE_FY':[{'year':y,'indicator':r['indicator'],'exercise_cash_usd':r['amount_usd']}
                  for y,r in sorted(result['issuance'].items())],
      'S6_verified':result['S6_total_verified_components'],
      'B_Q':result['B_Q'],'S6':result['S6'],
      'FY2024_PPE':result['ppe_depreciation'][2024],
      'FY2025_PPE':result['ppe_depreciation'][2025],
      'FY2024_CREDIT':result['credit_facility'][2024],
      'FY2025_CREDIT':result['credit_facility'][2025],
      'sha256':seal,'path':str(output),
    },ensure_ascii=False))

if __name__=='__main__': main()
