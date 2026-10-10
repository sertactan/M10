"""Source-backed INOD 2023–2025 B_Q and S6 *component* recovery.

The cash, financial and inventory gaps remain unfilled. Never manufacture
zero debt/inventory, standalone depreciation, or an S14 score.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, localcontext
from hashlib import sha256
import json
from pathlib import Path


ACCESSIONS = {
    2023: "0001410578-25-000194", # FY2024 10-K with FY2023 comparative
    2024: "0001104659-26-020655", # FY2025 10-K with FY2024 comparative
    2025: "0001104659-26-020655",
}
TAGS = {
    "revenue": "RevenueFromContractWithCustomerExcludingAssessedTax",
    "direct_cost": "DirectOperatingCosts",
    "gross_profit": "GrossProfit",
    "accounts_receivable": "AccountsReceivableNetCurrent",
    "current_assets": "AssetsCurrent",
    "ppe_net": "PropertyPlantAndEquipmentNet",
    "total_assets": "Assets",
    "sga": "SellingGeneralAndAdministrativeExpense",
    "net_income": "NetIncomeLoss",
    "operating_cash_flow": "NetCashProvidedByUsedInOperatingActivities",
    "cash": "CashAndCashEquivalentsAtCarryingValue",
}
INSTANT = {"accounts_receivable","current_assets","ppe_net","total_assets","cash"}


def _d(x):
    return Decimal(str(x))


def _ratio(n,d):
    if d<=0:
        raise ValueError('Positive ratio denominator required')
    return n/d


def _risk(raw, threshold, width):
    return max(Decimal(0),min(Decimal(1),(raw-threshold)/width))


def _iso_utc(value):
    t=datetime.fromisoformat(str(value).replace('Z','+00:00'))
    if not t.tzinfo:
        raise ValueError('Missing evidence timezone')
    return t.astimezone(timezone.utc)


def recover(inod_json: bytes, submission_json: bytes, *, retrieved_at: str,
            presentation_review: dict | None = None) -> dict:
    """Extract only exact-tag USD 10-K dates; independently verify rev-cost=GP.

    `presentation_review` holds document sha256 and the human-reviewed 10-K
    income statement identity; without it GMI remains diagnostic/unaccepted.
    """
    facts=json.loads(inod_json); subs=json.loads(submission_json)
    if int(facts.get('cik',-1))!=903651 or int(subs.get('cik',-2))!=903651:
        raise ValueError('SEC INOD issuer mismatch')
    at=_iso_utc(retrieved_at)
    recent=subs['filings']['recent']
    filings={}
    for i,acc in enumerate(recent['accessionNumber']):
        if acc not in ACCESSIONS.values():
            continue
        accepted=_iso_utc(recent['acceptanceDateTime'][i])
        if recent['form'][i]!='10-K' or accepted>at or acc in filings:
            raise ValueError('Duplicate/invalid SEC annual accession')
        filings[acc]={'filing_date':recent['filingDate'][i],
                      'accepted_at':accepted.isoformat(),
                      'report_date':recent['reportDate'][i]}
    if len(filings)!=2:
        raise ValueError('FY2024/FY2025 annual evidence not verified')
    selected={}
    missing=[]
    for year in (2023,2024,2025):
        accession=ACCESSIONS[year]; filing=filings[accession]
        end=f'{year}-12-31'
        per={}
        for name,tag in TAGS.items():
            item=facts.get('facts',{}).get('us-gaap',{}).get(tag)
            if not item:
                missing.append(f'{name}:{year}:tag_missing')
                continue
            choices=[]
            for rec in item.get('units',{}).get('USD',[]):
                if rec.get('accn')!=accession or rec.get('end')!=end or rec.get('form')!='10-K' or rec.get('filed')!=filing['filing_date']:
                    continue
                start=rec.get('start')
                if name in INSTANT and start:
                    continue
                if name not in INSTANT:
                    if not start:
                        continue
                    days=(date.fromisoformat(end)-date.fromisoformat(start)).days+1
                    if not 330<=days<=400:
                        continue
                if type(rec.get('val')) not in (int,float):
                    continue
                choices.append(rec)
            if not choices or len({(r['val'],r.get('start')) for r in choices})!=1:
                missing.append(f'{name}:{year}:exact_period_or_alias')
                continue
            record=choices[0]
            per[name]={'value':record['val'], 'tag':f'us-gaap:{tag}', 'unit':'USD',
                       'start':record.get('start'),'end':end,'accession':accession,
                       'filing_date':filing['filing_date'],
                       'accepted_at':filing['accepted_at'],
                       'available_at':at.isoformat(),
                       'source_ref':f'https://data.sec.gov/api/xbrl/companyfacts/CIK0000903651.json',
                       'evidence_sha256':sha256(json.dumps({'tag':tag,'record':record},sort_keys=True).encode()).hexdigest()}
        selected[year]=per
    def num(year,field):
        row=selected[year].get(field)
        return _d(row['value']) if row else None
    validated_presentation=False
    review=presentation_review or {}
    if (review.get('verified') is True
        and review.get('10k_accession')==ACCESSIONS[2025]
        and isinstance(review.get('document_sha256'),str)
        and len(review['document_sha256'])==64
        and review.get('scope')=='CONSOLIDATED_GAAP_STATEMENT_OF_OPERATIONS'
        and review.get('direct_operating_cost_is_gross_profit_cost') is True
        and review.get('source_ref')==
          'https://www.sec.gov/Archives/edgar/data/903651/000110465926020655/inod-20251231x10k.htm'):
        validated_presentation=True
    def calc_pair(a,b,operation):
        try:
            return operation(*[num(y,f) for y,f in a],*[num(y,f) for y,f in b])
        except (TypeError,ZeroDivisionError,ValueError):
            return None
    def fx(method):
        try:
            return method()
        except (TypeError,ValueError,ZeroDivisionError):
            return None
    for year in (2024,2025):
        rev,cost,gp=(num(year,n) for n in ('revenue','direct_cost','gross_profit'))
        if rev is not None and cost is not None and gp is not None:
            if rev-cost!=gp:
                raise ValueError(f'FY{year} revenue minus direct operating costs not gross profit')
        else:
            missing.append(f'GROSS_MARGIN_RECONCILIATION_{year}')
    computed={
        'DSRI':fx(lambda: _ratio(_ratio(num(2025,'accounts_receivable'),num(2025,'revenue')),
                                  _ratio(num(2024,'accounts_receivable'),num(2024,'revenue')))),
        'GMI':fx(lambda: _ratio(_ratio(num(2024,'gross_profit'),num(2024,'revenue')),
                                 _ratio(num(2025,'gross_profit'),num(2025,'revenue')))),
        'AQI':fx(lambda: _ratio(1-(num(2025,'current_assets')+num(2025,'ppe_net'))/num(2025,'total_assets'),
                                 1-(num(2024,'current_assets')+num(2024,'ppe_net'))/num(2024,'total_assets'))),
        'SGAI':fx(lambda: _ratio(_ratio(num(2025,'sga'),num(2025,'revenue')),
                                  _ratio(num(2024,'sga'),num(2024,'revenue')))),
        'SGI':fx(lambda: _ratio(num(2025,'revenue'),num(2024,'revenue'))),
        'TATA':fx(lambda: (num(2025,'net_income')-num(2025,'operating_cash_flow'))/num(2025,'total_assets')),
    }
    if not validated_presentation:
        # Gross profit ratio is real, but cost classification awaits filing body.
        missing.append('GMI_CONSOLIDATED_GAAP_PRESENTATION_REVIEW')
    weights={'DSRI':(Decimal(2),Decimal(1),Decimal('.5')),
             'GMI':(Decimal('1.5'),Decimal(1),Decimal('.3')),
             'AQI':(Decimal(2),Decimal(1),Decimal('.5')),
             'SGAI':(Decimal(1),Decimal(1),Decimal('.4')),
             'TATA':(Decimal(3),Decimal(0),Decimal('.10'))}
    risk={k: _risk(computed[k],middle,width) if computed.get(k) is not None and (k!='GMI' or validated_presentation) else None
          for k,(_,middle,width) in weights.items()}
    for k in ('DEPI','LVGI'):
        risk[k]=None
    risk_count=sum(x is not None for x in risk.values())
    partial_weighted_risk=sum(weights[k][0]*v for k,v in risk.items() if v is not None)
    # S6 three FY research components that do not depend on RSST or issuance.
    s6={
        'DELTA_REC':fx(lambda: (num(2025,'accounts_receivable')-num(2024,'accounts_receivable'))/
                    ((num(2025,'total_assets')+num(2024,'total_assets'))/2)),
        'SOFT':fx(lambda: (num(2025,'total_assets')-num(2025,'ppe_net')-num(2025,'cash'))/num(2025,'total_assets')),
        'DELTA_CASHSALES':fx(lambda: (
            (num(2025,'revenue')-(num(2025,'accounts_receivable')-num(2024,'accounts_receivable')))
            -(num(2024,'revenue')-(num(2024,'accounts_receivable')-num(2023,'accounts_receivable')))) /
             abs(num(2024,'revenue')-(num(2024,'accounts_receivable')-num(2023,'accounts_receivable')))),
        'DELTA_ROA':fx(lambda: num(2025,'net_income')/((num(2025,'total_assets')+num(2024,'total_assets'))/2) -
                    num(2024,'net_income')/((num(2024,'total_assets')+num(2023,'total_assets'))/2)),
    }
    return {'schema':'M10_SCORING_V3_SEC_QUALITY_EVIDENCE_1',
            'source_sha256':sha256(inod_json).hexdigest(),
            'submissions_sha256':sha256(submission_json).hexdigest(),
            'retrieved_at':at.isoformat(),
            'filings':filings,'by_fy':selected,
            'beneish':{'ratios':{k:float(v) if v is not None else None for k,v in computed.items()},
                       'risk_components':{k:float(v) if v is not None else None for k,v in risk.items()},
                       'verified_risk_count':risk_count,'required_risk_count':7,
                       'partial_weighted_risk_not_score':float(partial_weighted_risk),
                       'missing':['DEPI_DEPRECIATION_SEPARATION','LVGI_INTEREST_BEARING_DEBT',
                                  'INDEPENDENT_SERIOUS_FLAGS_REVIEW']+(
                                  [] if validated_presentation else ['GMI_PRESENTATION_REVIEW']),
                       'B_Q_SCORE':None},
            'dechow':{'verified_partial':{k:float(v) if v is not None else None for k,v in s6.items()},
                      'partial_input_count':sum(v is not None for v in s6.values()),
                      'required_model_inputs':7,'missing':['RSST_WC_NCO_FIN','DELTA_INV_INVENTORY',
                          'DOCUMENTED_ISSUANCE','PEER_OR_FROZEN_BIN_FULL_MODEL'],'S6_SCORE':None},
            'presentation_review':review if validated_presentation else {'verified':False},
            'other_missing':sorted(set(missing)),
            'S14_SCORE':None,'historical_pit_accepted':False,
            'scope':'CURRENT_RESEARCH_SOURCE_VERIFIED_NOT_PIT'}


def save_private(report:dict, path:Path)->str:
    if (path.name!='quality_v3.json' or path.exists() or path.is_symlink()
        or 'scoring_completion' not in (p.lower() for p in path.resolve().parts)):
        raise ValueError('New isolated private scoring_completion/quality_v3.json required')
    path.parent.mkdir(parents=True,exist_ok=True)
    payload=json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False).encode('utf8')
    with path.open('xb') as out:
        out.write(payload)
    seal=sha256(payload).hexdigest()
    with Path(str(path)+'.sha256').open('x',encoding='ascii') as out:
        out.write(seal)
    return seal
