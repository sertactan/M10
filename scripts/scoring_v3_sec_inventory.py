"""Inspect pre-cached SEC companyfacts and submissions without modifying either.

Prints only tag names, periods, SEC accessions, and aggregate coverage. No
proprietary financial data or provider credentials leave local runtime.
"""
from __future__ import annotations
import argparse
import json
from collections import defaultdict
from pathlib import Path


def inventory(companyfacts: Path, submissions: Path) -> dict:
    facts=json.loads(companyfacts.read_bytes())
    sub=json.loads(submissions.read_bytes())
    if int(facts.get('cik',-1)) != int(sub.get('cik',-2)):
        raise ValueError('SEC issuer mismatch')
    recent=sub['filings']['recent']
    annual=[{'accession':recent['accessionNumber'][i],
             'filing_date':recent['filingDate'][i],
             'report_date':recent['reportDate'][i],
             'acceptance':recent['acceptanceDateTime'][i]}
            for i,form in enumerate(recent['form']) if form=='10-K']
    keywords=('inventory','inventories','deprecia','amortiza','cost','grossprofit',
              'debt','borrow','lease','receivable','revenue','asset','profit',
              'issuance','stockissued','sharebased','payment','propertyplant')
    selected=[]
    for namespace, concepts in facts['facts'].items():
        for tag, info in concepts.items():
            if not any(k in tag.lower() for k in keywords):
                continue
            by_end=defaultdict(set)
            for unit, records in info['units'].items():
                for r in records:
                    if r.get('form')=='10-K' and r.get('end','')[:4] in ('2023','2024','2025'):
                        by_end[r['end']].add(f"{r['accn']} ({unit})")
            if by_end:
                selected.append({'namespace':namespace,'tag':tag,
                  'years':{y:sorted(z) for y,z in sorted(by_end.items())}})
    return {'cik':facts['cik'],'annual_filings':annual[:9],
            'tags':selected,'all_namespaces':list(facts['facts'])}


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--companyfacts',type=Path,required=True)
    p.add_argument('--submissions',type=Path,required=True)
    p.add_argument('--short',action='store_true')
    args=p.parse_args()
    result=inventory(args.companyfacts,args.submissions)
    if args.short:
        result['tags']=[{'tag':t['tag'],'periods':list(t['years'])} for t in result['tags']]
    print(json.dumps(result,ensure_ascii=False,indent=2))
