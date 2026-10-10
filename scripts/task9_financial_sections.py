"""Offline, private 10-K footnote passage inspection. No raw data persisted."""
from __future__ import annotations

from app.scoring_v3_sec_filing_evidence import _extract_text
from pathlib import Path
import argparse
import re
import sys

TERMS={
  'DEP':['depreciation expense','depreciation and amortization','property and equipment','software amortization','amortization expense','accumulated depreciation'],
  'DEBT':['line of credit','borrowing','loan payable','credit agreement','credit facility','notes payable','interest bearing','total debt','long-term obligations','long term obligations','Microsoft licenses','vendor financed'],
  'INVENTORY':['inventories','inventory','raw materials'],
  'ISSUE':['proceeds from the issuance','stock options exercised','stock option exercises','CONSOLIDATED STATEMENTS OF STOCKHOLDERS','issuance of common','shares issued','repurchase of stock','stock-based compensation'],
  'RSST':['other current liabilities','accounts payable','non-current liabilities','noncurrent liabilities','deferred revenue','current assets'],
}

def snippets(root, *, years=(2024,2025), groups=('DEP','DEBT','INVENTORY','ISSUE'), hits_per_term=4, window=420):
  names={2024:'000141057825000194_inod-20241231x10k.htm',
         2025:'000110465926020655_inod-20251231x10k.htm'}
  for year in years:
    path=root/names[year]
    text=_extract_text(path.read_bytes())
    print(f'\n=== FY{year} chars {len(text)} ===')
    for group in groups:
      print(f'\n-- {group} --')
      for term in TERMS[group]:
        matches=list(re.finditer(re.escape(term),text,re.I))
        print(f'[{term}] total={len(matches)}')
        for m in matches[:hits_per_term]:
          print(f'  offset={m.start()}:', re.sub(r'\s+',' ',text[max(0,m.start()-window):m.end()+window]))

if __name__=='__main__':
  if hasattr(sys.stdout,'reconfigure'):
    sys.stdout.reconfigure(errors='replace')
  p=argparse.ArgumentParser()
  p.add_argument('--cache',type=Path,required=True)
  p.add_argument('--groups',default='DEP,DEBT,INVENTORY,ISSUE')
  p.add_argument('--hits',type=int,default=3)
  p.add_argument('--window',type=int,default=220)
  p.add_argument('--offset',type=int)
  p.add_argument('--year',type=int,default=2025)
  a=p.parse_args()
  if a.offset is not None:
    named={2024:'000141057825000194_inod-20241231x10k.htm',2025:'000110465926020655_inod-20251231x10k.htm'}
    t=_extract_text((a.cache/named[a.year]).read_bytes())
    print(re.sub(r'\s+',' ',t[a.offset:a.offset+a.window]))
  else:
    snippets(a.cache,groups=tuple(a.groups.split(',')),hits_per_term=a.hits,window=a.window)
