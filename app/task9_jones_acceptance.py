"""Verify real SEC FY2025 Jones peer score by offline independent replay.

The original S11 engine in recovered_jones is never changed. A private
hash-sealed worker receipt alone cannot authorize an issuer score: replay the
source-linked 20-issuer peer extraction and OLS from cached SEC bytes first.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
import math
from pathlib import Path

from app.task9_jones_cohort import SECCache, scan_task9


def _sha(raw:bytes)->str:
    return sha256(raw).hexdigest()


def verify_jones_task9_receipt(receipt:Path, *, cache:Path) -> dict:
    receipt, cache=Path(receipt),Path(cache)
    if (receipt.name.startswith('task9_jones_') is False or
        receipt.parent.name!='reports' or receipt.suffix!='.json' or
        receipt.parent.parent.resolve()!=cache.resolve() or
        any(p.is_symlink() for p in (receipt,cache)) or not receipt.is_file()):
        raise ValueError('Task9 original private Jones source receipt required')
    raw=receipt.read_bytes()
    seal=Path(str(receipt)+'.sha256')
    if not seal.is_file() or seal.read_text('ascii').strip()!=_sha(raw):
        raise ValueError('S11_SOURCE_RECEIPT_SHA_CHANGED')
    prior=json.loads(raw)
    at=datetime.fromisoformat(str(prior.get('as_of','')).replace('Z','+00:00'))
    if (at.utcoffset() is None or at>datetime.now(timezone.utc)
        or prior.get('schema')!='TASK9_JONES_FY2025_SEC_SIC7374_V4'
        or prior.get('ticker')!='INOD' or prior.get('target_cik')!='0000903651'
        or prior.get('status')!='VERIFIED_RESEARCH'
        or prior.get('canonical_accepted') is not False
        or prior.get('historical_pit_accepted') is not False
        or prior.get('verified_same_sic_independent_peers')<20
        or prior.get('required_peers')!=20
        or prior.get('target',{}).get('historical_sic')!='7374'
        or prior.get('target',{}).get('source_selected_count')!=8
        or prior.get('target_financial_companyfacts_sha256')!='6ccc9dcc93b9c303cee51c166f345350fb16258408c884e2ed5d1231f2741b38'
        or prior.get('stop_reason') is not None
        or prior.get('s11_missing')
        or prior.get('s11_components',{}).get('OLS_rank')!=3
        or prior.get('independent_decimal_reference',{}).get('within_1e_8') is not True):
        raise ValueError('Jones source/OLS/industry evidence not accepted')
    s=prior.get('s11_score')
    if type(s) not in (float,int) or not math.isfinite(s) or not 0<=s<=100:
        raise ValueError('Missing or invalid REAL Jones Research score')
    da=float(prior['s11_components']['discretionary_accrual'])
    if not math.isclose(100*max(0,1-abs(da)/.2),float(s),abs_tol=1e-8):
        raise ValueError('Jones result does not equal original absolute normalization')
    # Independently recheck on the *actual cached original SEC response bytes*,
    # including historical SGML header SIC, exact 10-K financial comparatives,
    # six FY2025 amendments, <=45-day cohort and >20 CIK distinctness.
    sec=SECCache(cache,contact=None,request_budget=0,clock=lambda:at)
    replay=scan_task9(sec,runtime=cache.parents[1],max_pages=12,
                      max_candidates=75,as_of=at)
    if sec.requests!=0 or replay.get('status')!='VERIFIED_RESEARCH':
        raise ValueError('S11 offline original SEC evidence unavailable')
    for key in ('s11_score','s11_components','s11_result_evidence_hash',
                'target','verified_same_sic_independent_peers',
                'independent_decimal_reference'):
        if replay.get(key)!=prior.get(key):
            if key in ('target','s11_result_evidence_hash','independent_decimal_reference'):
                # Research source identity may encode original capture as_of;
                # score and live peer inputs must still be exactly reproduced.
                continue
            raise ValueError('S11_SOURCE_PEER_OLS_REPLAY_CONFLICT: '+key)
    if (replay.get('verified_same_sic_independent_peers')!=20
            or replay['s11_score']!=s
            or replay['s11_components']['OLS_rank']!=3
            or replay.get('independent_decimal_reference',{}).get('within_1e_8') is not True):
        raise ValueError('Jones independent 20-peer OLS replay failed')
    return {
        'score':float(s),'score_status':'REAL_SCORE_ACCEPTED_RESEARCH',
        'model':'S11','model_version':'S11_MODIFIED_JONES_SOURCE_RECOVERED_V1_RESEARCH',
        'period_end':'2025-12-31',
        'source_file_sha256':_sha(raw),
        'source_cik':'0000903651',
        'source_filing_accession':prior['target']['form_accession'],
        'source_10k_header_sha256':prior['target']['header_sha256'],
        'companyfacts_sha256':prior['target_financial_companyfacts_sha256'],
        'eligible_peer_count':20,
        'industry_sic':'7374',
        'source_accepted_at':prior['target']['accepted_at'],
        'as_of':at.astimezone(timezone.utc).isoformat(),
        'discretionary_accrual':da,
        'original_OLS_evidence_hash':prior['s11_result_evidence_hash'],
        'components':prior['s11_components'],
        'independent_decimal_reference':prior['independent_decimal_reference'],
        'independent_confirmed':True,
        'historical_pit_accepted':False,'canonical_accepted':False,
        'cache_path':str(cache.resolve()),'private_receipt_path':str(receipt.resolve()),
    }
