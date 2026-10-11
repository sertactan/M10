"""V10 frozen Beneish DEPI accounting-component recovery and INOD gates.

This does not produce B_Q/S5/S14 scores; it independently sources only a
single authentic risk component and refuses a mixed depreciation+amortization
tag. All private receipts remain outside version control. No network or DB.
"""
from __future__ import annotations
from decimal import Decimal, localcontext
from hashlib import sha256
from pathlib import Path
import json, zipfile

from app.scoring_v7_piotroski import TARGETS, _entry
from app.scoring_v8_s9_audit import PILOTS, SOURCE_PINS
from app.scoring_v9_inod import FY2024_10K_SHA

CONTRACT_SHA = '53dce841fd5ebdfeb00636f327493be1255ea8b60e6df4eadd921a7098813794'
EXACT_DEPI_TAG = 'Depreciation'
EXACT_PPE_TAG = 'PropertyPlantAndEquipmentNet'


def _cfg(ticker):
    c = TARGETS.get(ticker) or PILOTS.get(ticker)
    if not c: raise ValueError('UNSUPPORTED_ISSUER')
    return {'cik':c['cik'], 'accn':c.get('current_accession',c.get('current')),
            'end':c.get('end',c.get('fy')),
            'prior':c.get('prior_end',c.get('prior')),
            'source_hash':c.get('companyfacts_sha256',SOURCE_PINS.get(ticker,{}).get('companyfacts'))}


def _real_fact(facts, tag, config, end, flow):
    row = _entry(facts,tag,config['accn'],end,flow=flow)
    if (not row or row['unit']!='USD' or row['filed'] is None
            or row['accession']!=config['accn'] or row['form']!='10-K'):
        return None
    return row


def depreciation_component(ticker:str, raw:bytes)->dict:
    cfg = _cfg(ticker)
    if cfg['source_hash'] is None or sha256(raw).hexdigest()!=cfg['source_hash']:
        raise ValueError('SEC_COMPANYFACTS_PIN_CHANGED')
    payload=json.loads(raw)
    if str(payload.get('cik','')).zfill(10)!=cfg['cik']:
        raise ValueError('COMPANYFACTS_ISSUER_CHANGED')
    f=payload['facts']['us-gaap']
    fields={}
    for period,end in (('current',cfg['end']),('prior',cfg['prior'])):
        for kind,tag,flow in [('dep',EXACT_DEPI_TAG,True),('ppe',EXACT_PPE_TAG,False)]:
            fields[f'{kind}_{period}']=_real_fact(f,tag,cfg,end,flow)
    missing=[k for k,row in fields.items() if row is None]
    common={'ticker':ticker,'model_component':'B_Q.DEPI',
            'frozen_source_sha256':CONTRACT_SHA, 'current_accession':cfg['accn'],
            'fiscal_end':cfg['end'],'prior_end':cfg['prior'],
            'companyfacts_sha256':sha256(raw).hexdigest(),
            'inputs':fields,'canonical_accepted':False,
            'historical_pit_accepted':False,'full_model_score':None}
    if missing:
        return {**common,'status':'DATA_MISSING','missing':missing,
                'ratio':None,'risk_component':None}
    with localcontext() as ctx:
        ctx.prec=60
        D=lambda k:Decimal(fields[k]['value'])
        dc,dp,pc,pp=(D(x) for x in ('dep_current','dep_prior','ppe_current','ppe_prior'))
        if min(dc,dp,pc,pp)<=0:
            return {**common,'status':'SPEC_EDGE_CASE',
                    'missing':['DEPI_STRICT_POSITIVE_INPUTS'],'ratio':None,'risk_component':None}
        annual_prior=dp/(dp+pp)
        annual_current=dc/(dc+pc)
        ratio=annual_prior/annual_current
        independent=(dp*(dc+pc))/(dc*(dp+pp))
        if abs(ratio-independent)>Decimal('1e-50'):
            raise ValueError('INDEPENDENT_DEPI_DECIMAL_REFERENCE_CHANGED')
        risk=min(Decimal(1),max(Decimal(0),(ratio-Decimal(1))/Decimal('.75')))
        return {**common,'status':'VERIFIED_COMPONENT_RESEARCH_ONLY',
                'missing':[],'depreciation_policy':
                     'PURE_us_gaap_Depreciation_NOT_DepreciationAndAmortization',
                'depi_ratio_decimal':str(ratio),'depi_ratio':float(ratio),
                'risk_component_decimal':str(risk),'risk_component':float(risk),
                'independent_decimal_reference':str(independent),
                'independent_reference_precision':'within 1e-50 for 60-digit Decimal',
                'full_model_gate': 'B_Q_S5_REMAIN_NA_UNTIL_ALL_COMPONENTS_AND_REVIEW_COMPLETE'}


def inod_quality_gate(inod_s9:dict, expert_form:dict)->dict:
    if (inod_s9.get('ticker')!='INOD'
            or inod_s9.get('score_status')!='REAL_SCORE_ACCEPTED_RESEARCH'
            or inod_s9.get('signals',{}).get('F_DELTA_LEVERAGE')!=0
            or inod_s9.get('canonical_accepted') is not False):
        raise ValueError('ORIGINAL_INOD_S9_RECEIPT_REQUIRED')
    debt=inod_s9['debt_reconciliation']
    if debt['debt_FY2025_USD']!='0' or debt['debt_FY2024_USD']!='0':
        raise ValueError('S9_ZERO_BORROWING_EVIDENCE_CHANGED')
    if (expert_form.get('issuer')!='INOD'
            or set(expert_form.get('blocks',{}))!={'AUD','RPT','REC','DIL','REV','ACQ','GOV'}):
        raise ValueError('EXPERT_SOURCE_PACKET_OR_RUBRIC_CHANGED')
    reviewed={k:v.get('signed') is True and
              v.get('risk_level_0_25_50_75_100') in (0,25,50,75,100)
              for k,v in expert_form['blocks'].items()}
    if any(reviewed.values()) or expert_form.get('all_decisions_signed') is not False:
        raise ValueError('V10_UNEXPECTED_S13_HUMAN_REVIEW_CHANGED')
    # The original B_Q input label is TOTAL_DEBT, not specifically the
    # long-term interest-bearing borrowing used by V7 Piotroski. Reusing
    # S9's two zeros here would create a 0/0 without a model definition.
    return {'ticker':'INOD','scope':'CURRENT_RESEARCH_ONLY','canonical_accepted':False,
            'B_Q_LVGI':None,'B_Q_LVGI_status':'SPEC_EDGE_CASE_IF_S9_DEBT_SCOPE_EQUIVALENT',
            'LVGI_mathematical_case':'0/0 if and only if frozen TOTAL_DEBT exactly equals V9 S9 borrowing scope; otherwise missing TOTAL_DEBT mapping',
            'B_Q_DEPI':None,'B_Q_status':'DATA_MISSING',
            'S6_status':'DATA_MISSING','S6_verified_inputs':5,'S6_required_inputs':7,
            'S6_required':['STI_LTI_DLC_DLTT_AND_WC_NCO_FIN','INVENTORY_SOURCE_NOT_ZERO_DEFAULT'],
            'S13_status':'REVIEW_REQUIRED','S13_signed_blocks':0,
            'S13_required_signed_blocks':7,'S13_reviewed':reviewed,
            'S14_score':None,'S14_verified_legs':3,'S14_required_legs':6,
            'S14_remaining':['S6','B_Q','S13']}


def seal_private_report(path:Path,report:dict):
    raw=(json.dumps(report,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode('utf8')
    seal=Path(str(path)+'.sha256')
    if path.exists():
        if path.read_bytes()!=raw or not seal.is_file() or seal.read_text('ascii').strip()!=sha256(raw).hexdigest():
            raise ValueError('PRIVATE_V10_QUALITY_REPLAY_OR_SEAL_CHANGED')
    else:
        if seal.exists():raise ValueError('PRIVATE_V10_QUALITY_PARTIAL_SEAL_COLLISION')
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as f:f.write(raw)
        with seal.open('x',encoding='ascii') as f:f.write(sha256(raw).hexdigest()+'\n')
    return sha256(raw).hexdigest()
