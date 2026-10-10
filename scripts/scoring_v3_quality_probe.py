"""No-network SEC source recovery: real Beneish/S6 partial financial evidence.

Reads only the preexisting official SEC Companyfacts and SEC Submissions cache.
Optionally accepts a newly verified PRIVATE official 2025 10-K HTML body for
consolidated-direct-cost presentation verification. Produces a NEW sealed
local research receipt. Does not generate B_Q, S6 or S14 score prematurely.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import re

from app.scoring_v3_sec_quality import recover,save_private


OFFICIAL_URL='https://www.sec.gov/Archives/edgar/data/903651/000110465926020655/inod-20251231x10k.htm'


class _Content(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts=[]
    def handle_data(self,data):
        self.parts.append(data)


def verify_presentation(body:bytes, raw:bytes, subs:bytes)->dict:
    parser=_Content()
    parser.feed(body.decode('utf-8','replace'))
    plain=re.sub(r'\s+',' ', ' '.join(parser.parts).replace('\u200b','')).strip()
    # SEC inline XBRL table is in thousands; independent second check uses
    # exact source values for two years and the cashflow-aligned filing date.
    preliminary=recover(raw,subs,retrieved_at='2026-10-10T17:53:29.445570+00:00')
    marker='CONSOLIDATED STATEMENTS OF OPERATIONS AND COMPREHENSIVE INCOME'
    starts=[m.start() for m in re.finditer(re.escape(marker),plain,re.I)]
    ok=False
    # The consolidated P&L displays revenues and Direct Operating Costs,
    # but not an explicit Gross Profit row. GAAP GrossProfit is independently
    # cross-footed to the two P&L fields from same-accession Companyfacts.
    fields=('revenue','direct_cost')
    for start in starts:
        section=plain[start:start+6500]
        if ('Direct operating costs' not in section or
                '2025' not in section or '2024' not in section):
            continue
        if not all(all(f"{preliminary['by_fy'][y][key]['value']/1000:,.0f}" in section
                           for key in fields)
                   for y in (2024,2025)):
            continue
        ok=True
        break
    if not ok:
        return {'verified':False,'status':'PRESENTATION_NOT_MATCHED_CONSOLIDATED_STATEMENT'}
    return {'verified':True,'10k_accession':'0001104659-26-020655',
            'scope':'CONSOLIDATED_GAAP_STATEMENT_OF_OPERATIONS',
            'direct_operating_cost_is_gross_profit_cost':True,
            'source_ref':OFFICIAL_URL,
            'document_sha256':sha256(body).hexdigest(),
            'verification':'GAAP_10K_OPERATIONS_STATEMENT_CROSS_FOOT_2024_2025'}


def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--companyfacts',type=Path,required=True)
    a.add_argument('--submissions',type=Path,required=True)
    a.add_argument('--filing-body',type=Path)
    a.add_argument('--output',type=Path,required=True)
    args=a.parse_args()
    raw=args.companyfacts.read_bytes(); subs=args.submissions.read_bytes()
    if sha256(raw).hexdigest()!='6ccc9dcc93b9c303cee51c166f345350fb16258408c884e2ed5d1231f2741b38':
        raise ValueError('Prior verified official SEC Companyfacts bytes changed')
    review=verify_presentation(args.filing_body.read_bytes(),raw,subs) if args.filing_body else None
    report=recover(raw,subs,retrieved_at='2026-10-10T17:53:29.445570+00:00',
                   presentation_review=review)
    seal=save_private(report,args.output)
    print(json.dumps({'status':'SOURCE_BQ_S6_PARTIAL_RESEARCH_ONLY',
                      'verified_bq_components':report['beneish']['verified_risk_count'],
                      'required_bq_components':7,
                      's6_verified_partial':report['dechow']['partial_input_count'],
                      's6_required_components':7,
                      'ratios':report['beneish']['ratios'],
                      'risk_components':report['beneish']['risk_components'],
                      'partial_dechow':report['dechow']['verified_partial'],
                      'missing':report['beneish']['missing'],
                      'presentation_verified':report['presentation_review'].get('verified',False),
                      'output_sha256':seal, 'B_Q':None,'S6':None,'S14':None,
                      'historical_pit_accepted':False},allow_nan=False))


if __name__=='__main__':
    main()
