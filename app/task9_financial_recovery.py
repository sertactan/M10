"""Task 9: exact SEC evidence for ISSUE, debt facility and PPE D&A.

This is NOT a replacement for frozen Beneish/Dechow mathematics. It emits
only mathematically source-complete features, with no fallback for absent
inventory, RSST, pure depreciation or zero-denominator LVGI.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re

from app.scoring_v3_sec_filing_evidence import _extract_text


EXPECTED={
    2023:'0001410578-25-000194',
    2024:'0001104659-26-020655',
    2025:'0001104659-26-020655',
}
STOCK_OPTION_VALUE='StockIssuedDuringPeriodValueStockOptionsExercised'
SEC_URL='https://data.sec.gov/api/xbrl/companyfacts/CIK0000903651.json'
OBLIGATION_EXTENSION={
  'current':'inod:CurrentPortionOfLongTermObligations',
  'noncurrent':'inod:NoncurrentPortionOfLongTermObligations',
  'total':'inod:TotalLongTermObligations',
  'software_license':'inod:MicrosoftLicensesObligations',
}


def _clock(v:str)->datetime:
    t=datetime.fromisoformat(v.replace('Z','+00:00'))
    if not t.tzinfo:
        raise ValueError('SEC clock must be timezone-aware')
    return t.astimezone(timezone.utc)


def _source_accessions(submissions:dict, *, as_of:str):
    recent=submissions['filings']['recent']
    at=_clock(as_of)
    out={}
    for y,acc in EXPECTED.items():
        indices=[i for i,a in enumerate(recent['accessionNumber']) if a==acc]
        if len(indices)!=1:
            raise ValueError('SEC_SUBMISSIONS_ACCESSION_AMBIGUOUS')
        i=indices[0]
        accepted=_clock(recent['acceptanceDateTime'][i])
        if accepted>at or recent['form'][i]!='10-K':
            raise ValueError('SEC_ANNUAL_FILING_ACCEPTANCE')
        out[y]={'accession':acc, 'accepted_at':accepted.isoformat(),
                'filing_date':recent['filingDate'][i]}
    return out


def _fy_fact(tag:dict, *, year:int, filing:dict, instant:bool=False):
    end=f'{year}-12-31'
    found=[]
    for r in tag.get('units',{}).get('USD',[]):
        if (r.get('accn')!=filing['accession'] or r.get('end')!=end
            or r.get('filed')!=filing['filing_date'] or r.get('form')!='10-K'
            or type(r.get('val')) not in (int,float)):
            continue
        start=r.get('start')
        if instant:
            if start is not None: continue
        else:
            if not start: continue
            if not 330 <= (date.fromisoformat(end)-date.fromisoformat(start)).days+1<=400: continue
        found.append(r)
    if not found or len({(x['val'],x.get('start')) for x in found})!=1:
        return None
    return found[0]


def _bounded_note(text:str, head:str, *, until:str | None=None, limit:int=9000):
    matches=list(re.finditer(re.escape(head),text,flags=re.I))
    if not matches: return None
    # F-note section is typically the LAST occurrence; table of contents and
    # earlier narrative headings are not adequate substitutes for note body.
    s=matches[-1].start()
    stop=min(len(text),s+limit)
    if until:
        p=re.search(re.escape(until),text[s+len(head):stop],flags=re.I)
        if p: stop=s+len(head)+p.start()
    return {'offset':s,'text':text[s:stop]}


def _no_credit_use(text, fiscal_year:int):
    note=_bounded_note(text,'Line of Credit',limit=6500)
    # Limit to same reported annual period. Phrase "did not utilize" is not
    # interchangeable with a zero *total* interest-bearing debt balance.
    if note is None:
        return {'status':'NOTE_MISSING','facility_usage':None}
    p=re.search(r'did\s+not\s+utilize\s+the\s+Revolving\s+Credit\s+Facility\s+during\s+the\s+year\s+ended\s+December\s+31,\s*'+str(fiscal_year),note['text'],re.I)
    return {'status':'AFFIRMATIVE_UNUSED_FACILITY' if p else 'NO_AFFIRMATIVE_USE_EVIDENCE',
            'facility_usage':0 if p else None,
            'note_offset':note['offset'],
            'note_sha256':sha256(note['text'].encode()).hexdigest(),
            'total_interest_bearing_debt':None,
            'LVGI':None}


def _ppe_depreciation(text, year:int):
    matches=list(re.finditer(r'3\s*\.\s*Property\s+and\s+equipment',text,re.I))
    note=None
    if matches:
        start=matches[-1].start()
        content=text[start:start+6800]
        next_note=re.search(r'4\s*\.\s*Goodwill',content,re.I)
        if next_note: content=content[:next_note.start()]
        note={'offset':start,'text':content}
    if note is None:
        return {'status':'PPE_NOTE_MISSING','DEPI':None}
    phrase=re.search(r'Depreciation and amortization expense of property and equipment were approximately\s*\$([\d.]+)\s*million and\s*\$([\d.]+)\s*million',note['text'],re.I)
    nums=([float(phrase.group(1)),float(phrase.group(2))] if phrase else None)
    return {'status':'APPROXIMATE_PPE_DEPRECIATION_AND_AMORTIZATION_MIXED' if nums else 'PPE_EXPLICIT_EXPENSE_NOT_FOUND',
            'PPE_depreciation_and_amortization_million_approx':nums,
            'note_offset':note['offset'],
            'note_sha256':sha256(note['text'].encode()).hexdigest(),
            'separately_verified_pure_depreciation':None,'DEPI':None}


def _extension_obligations(body:bytes, text:str, years:tuple[int,...]):
    """Verify true historical inline extension tag/USD context & note split.

    Total long-term obligations includes a large pension accrual. Finance
    status of the much smaller software-license balance is NOT given by an
    obligation's tag and cannot be guessed as interest-bearing debt.
    """
    chosen={}
    for m in re.finditer(rb'<ix:nonfraction\b([^>]*)>',body,re.I|re.S):
        attrs=m.group(1)
        values={}
        for field in ('name','contextref','unitref','scale'):
            got=re.search(rb'\b'+field.encode()+rb'\s*=\s*["\']([^"\']+)',attrs,re.I)
            if got: values[field]=got.group(1).decode('utf8','replace')
        metric=next((k for k,v in OBLIGATION_EXTENSION.items()
                     if values.get('name')==v),None)
        if not metric or values.get('scale')!='3' or 'USD' not in values.get('unitref',''):
            continue
        year=next((y for y in years if values.get('contextref','').startswith(f'As_Of_12_31_{y}_')),None)
        if year is None: continue
        closing=re.search(rb'</ix:nonfraction\s*>',body[m.end():m.end()+300],re.I)
        if not closing: continue
        inside=body[m.end():m.end()+closing.start()]
        displayed=re.sub(rb'<[^>]+>',b'',inside).strip()
        if not re.fullmatch(rb'[\d,]+',displayed): continue
        usd=int(displayed.replace(b',',b''))*1000
        key=(year,metric)
        if key in chosen and chosen[key]['usd']!=usd:
            raise ValueError('CONFLICTING_INLINE_EXTENSION_OBLIGATION_VALUES')
        chosen[key]={'usd':usd,'source_tag':OBLIGATION_EXTENSION[metric],
                     'context_ref':values['contextref'], 'source_sha256':sha256(body).hexdigest()}
    note_match=list(re.finditer(r'6\s*\.\s*Long-term\s+obligations',text,re.I))
    note=None
    if note_match:
        start=note_match[-1].start()
        end=re.search(r'7\s*\.\s*Commitments',text[start:start+4500],re.I)
        excerpt=text[start:start+(end.start() if end else 3500)]
        if 'Pension obligations' in excerpt and 'Microsoft licenses' in excerpt:
            note={'offset':start,'sha256':sha256(excerpt.encode()).hexdigest(),
                  'text':excerpt}
    out={}
    for year in years:
        values={k:chosen.get((year,k)) for k in OBLIGATION_EXTENSION}
        ready=all(values.values()) and note is not None
        if ready:
            total=values['total']['usd']
            lease=values['software_license']['usd']
            pension=total-lease
            # Verify both published category numbers and financial statement
            # current vs noncurrent identity; do not swap interest-bearing debt.
            ready=(pension>=0 and
                   values['current']['usd']+values['noncurrent']['usd']==total and
                   f'{pension/1000:,.0f}' in note['text'] and
                   f'{lease/1000:,.0f}' in note['text'])
        out[year]={
          'status':'SOURCE_RECONCILED_MIXED_OBLIGATIONS' if ready else 'EXTENSION_SPLIT_NOT_VERIFIED',
          'source':values,'amounts_usd':{
              'current_portion':values['current']['usd'] if values['current'] else None,
              'noncurrent_portion':values['noncurrent']['usd'] if values['noncurrent'] else None,
              'total_long_term_obligations':values['total']['usd'] if values['total'] else None,
              'software_license_obligation':values['software_license']['usd'] if values['software_license'] else None,
              'pension_obligation':pension if ready else None,
          },
          'reviewed_note_sha256':note['sha256'] if ready else None,
          'separately_proven_interest_bearing_debt':None,
          'LVGI':None,
        }
    return out


def _equity_statement(text:str,proceeds_usd:float|int):
    # Audited F-6 shareholders' equity disclosure supports *equity issuance*,
    # while cash option-exercise proceeds and SBC expense are separate.
    possible=list(re.finditer(r'Stock option exercises',text,re.I))
    for match in possible:
        before=text[max(0,match.start()-14500):match.start()]
        headings=list(re.finditer(r'CONSOLIDATED STATEMENTS OF STOCKHOLDERS',before,re.I))
        if not headings: continue
        start=max(0,match.start()-14500)+headings[-1].start()
        end_match=re.search(r'F-6\s+Table of Contents',text[match.start():],re.I)
        if not end_match: continue
        end=match.start()+end_match.start()
        if end-start>18000: continue
        excerpt=text[start:end]
        if f'{proceeds_usd/1000:,.0f}' not in excerpt: continue
        return {'offset':start,'text':excerpt}
    return None


def recover_task9_evidence(companyfacts:bytes, submissions:bytes, bodies:dict[int,bytes],
                           *, retrieved_at:str)->dict:
    data=json.loads(companyfacts);sub=json.loads(submissions)
    if int(data.get('cik',-1))!=903651 or int(sub.get('cik',-2))!=903651:
        raise ValueError('INOD SEC CIK mismatch')
    filed=_source_accessions(sub,as_of=retrieved_at)
    required=(2024,2025)
    if any(y not in bodies or not isinstance(bodies[y],bytes) for y in required):
        raise ValueError('Two SEC annual primary document bodies are mandatory')
    text={y:_extract_text(bodies[y]) for y in required}
    # Independent financial statement passage + exact XBRL tag agree on cash
    # option exercises. Absence is unknown, never ISSUE=0.
    issuer_fact=(data.get('facts',{}).get('us-gaap',{})
                 .get(STOCK_OPTION_VALUE,{}))
    issuance={}
    for y in (2023,2024,2025):
        r=_fy_fact(issuer_fact,year=y,filing=filed[y])
        document_y=2024 if y==2023 else 2025
        body=text[document_y]
        stock_section=_equity_statement(body,r['val']) if r is not None else None
        # An amount and a source are both needed; XBRL plus audited equity
        # issuance presentation, NOT stock-based compensation expense alone.
        corroborated=bool(stock_section and 'Stock option exercises' in stock_section['text']
                          and r and r['val']>0)
        issuance[y]={
          'indicator':1 if corroborated else None,
          'basis':'CASH_PROCEEDS_FROM_STOCK_OPTIONS_EXERCISED' if corroborated else 'INSUFFICIENT_ISSUANCE_SOURCE',
          'amount_usd':r['val'] if r else None,
          'source_tag':f'us-gaap:{STOCK_OPTION_VALUE}',
          'source_ref':SEC_URL,'accession':filed[y]['accession'],
          'accepted_at':filed[y]['accepted_at'],
          'fiscal_year_end':f'{y}-12-31',
          'raw_record_sha256':sha256(json.dumps(r,sort_keys=True).encode()).hexdigest() if r else None,
          'stockholders_equity_statement_sha256':sha256(stock_section['text'].encode()).hexdigest() if stock_section else None,
          'stockholders_equity_statement_offset':stock_section['offset'] if stock_section else None,
        }
    credits={y:_no_credit_use(text[y],y) for y in required}
    ppe={y:_ppe_depreciation(text[y],y) for y in required}
    oblig=_extension_obligations(bodies[2025],text[2025],required)
    # Missing stock tag is unobservable even if these SEC documents contain no
    # "inventory" keyword: 0 requires explicit audited disclosure.
    return {
      'schema':'MERIDYEN_TASK9_FILING_EVIDENCE_V1',
      'companyfacts_sha256':sha256(companyfacts).hexdigest(),
      'submissions_sha256':sha256(submissions).hexdigest(),
      'filing_bodies_sha256':{str(y):sha256(bodies[y]).hexdigest() for y in required},
      'as_of':_clock(retrieved_at).isoformat(),
      'financial_years':[2023,2024,2025],
      'issuance':issuance,
      'S6_ISSUE':1 if issuance[2025]['indicator']==1 else None,
      'S6_newly_verified_component_count':1 if issuance[2025]['indicator']==1 else 0,
      'S6_total_verified_components':4+(1 if issuance[2025]['indicator']==1 else 0),
      'ppe_depreciation':ppe,
      'credit_facility':credits,
      'long_term_obligations':oblig,
      'inventory':{'evidenced_quantity':None,'delta_inventory':None,
                   'reason':'NO_EXACT_INVENTORY_BALANCE_OR_AFFIRMATIVE_ZERO_IN_TWO_10K'},
      'RSST':{'WC':None,'NCO':None,'FIN':None,'value':None,
              'reason':'NO_REVIEWED_COMPLETE_WC_NCO_FIN_DECOMPOSITION'},
      'B_Q':None,'S6':None,'S14':None,
      'source_evidence_not_human_adjudication':True,
      'historical_pit_accepted':False,'scope':'CURRENT_RESEARCH_ONLY',
    }
