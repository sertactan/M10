"""Offline original-byte acceptance of FY2025 SIC2834 Jones scores."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path

from app.task9_jones_cohort import SECCache, scan_task9


def _material(observation):
    """Source identity and amounts, excluding mutable local observation clock."""
    return {
        'cik': observation['cik'], 'security_id': observation['security_id'],
        'period_start': observation['period_start'],
        'period_end': observation['period_end'],
        'industry': {k: observation['industry'][k] for k in
                     ('scheme', 'code', 'effective_on', 'evidence_hash')},
        'facts': sorted([{k: row[k] for k in
                          ('metric', 'value', 'period_start', 'period_end',
                           'accession', 'evidence_hash')}
                         for row in observation['facts']],
                        key=lambda row: (row['metric'], row['period_end'])),
    }


def _verify_calendar_receipt(receipt: Path, *, cache: Path, runtime: Path,
                             ticker: str) -> dict:
    targets = {
        'ETON': ('0001710340', 'RevenueFromContractWithCustomerExcludingAssessedTax'),
        'CRMD': ('0001410098', 'Revenues'),
    }
    if ticker not in targets:
        raise ValueError('UNSUPPORTED_V6_JONES_TARGET')
    cik, revenue_tag = targets[ticker]
    receipt, cache, runtime = Path(receipt), Path(cache), Path(runtime)
    if (receipt.name != 'report.json' or receipt.parent.name != 'jones_'+ticker.lower()
            or not receipt.is_file() or receipt.is_symlink()
            or not cache.is_dir() or cache.is_symlink()):
        raise ValueError('ETON_PRIVATE_JONES_SOURCE_REQUIRED')
    raw = receipt.read_bytes()
    seal = Path(str(receipt)+'.sha256')
    if not seal.is_file() or seal.read_text('ascii').strip() != sha256(raw).hexdigest():
        raise ValueError('ETON_JONES_RECEIPT_SEAL_CHANGED')
    prior = json.loads(raw)
    at = datetime.fromisoformat(prior['as_of'].replace('Z', '+00:00'))
    peers = prior.get('peer_observations') or []
    target = prior.get('target_observation')
    score = prior.get('s11_score')
    if (at.tzinfo is None or at > datetime.now(timezone.utc)
            or prior.get('schema') != 'SCORING_V6_JONES_FY2025_SEC_SIC2834'
            or prior.get('ticker') != ticker or prior.get('target_cik') != cik
            or prior.get('status') != 'VERIFIED_RESEARCH'
            or prior.get('canonical_accepted') is not False
            or prior.get('historical_pit_accepted') is not False
            or prior.get('required_peers') != 20
            or prior.get('verified_same_sic_independent_peers') != 20
            or len(peers) != 20 or len({p['cik'] for p in peers}) != 20
            or any(p['cik'] == cik for p in peers)
            or not target or target['industry']['code'] != '2834'
            or prior.get('target', {}).get('source_selected_count') != 8
            or prior.get('stop_reason') is not None or prior.get('s11_missing')
            or prior.get('s11_components', {}).get('OLS_rank') != 3
            or prior.get('independent_decimal_reference', {}).get('within_1e_8') is not True
            or type(score) not in (int, float) or not math.isfinite(score)
            or not 0 <= score <= 100):
        raise ValueError('ETON_JONES_ACCEPTANCE_GATES_FAILED')
    da = float(prior['s11_components']['discretionary_accrual'])
    if not math.isclose(100*max(0, 1-abs(da)/.20), score, abs_tol=1e-8):
        raise ValueError('ETON_ORIGINAL_ABSOLUTE_NORMALIZATION_CHANGED')
    sec = SECCache(cache, contact=None, request_budget=0, clock=lambda: at)
    replay = scan_task9(sec, runtime=runtime, max_pages=8, max_candidates=50,
                        as_of=at, target_cik=cik,
                        target_ticker=ticker, sic='2834',
                        target_revenue_tag=revenue_tag)
    if (sec.requests != 0 or replay['s11_score'] != score
            or replay['s11_components'] != prior['s11_components']
            or replay['independent_decimal_reference'] != prior['independent_decimal_reference']
            or replay['target_financial_companyfacts_sha256'] !=
               prior['target_financial_companyfacts_sha256']
            or replay['target'] != prior['target']
            or _material(replay['target_observation']) != _material(target)
            or [_material(p) for p in replay['peer_observations']] !=
               [_material(p) for p in peers]):
        raise ValueError('ETON_ORIGINAL_SEC_PEER_OLS_REPLAY_CHANGED')
    return {
        'score': float(score), 'score_status': 'REAL_SCORE_ACCEPTED_RESEARCH',
        'model': 'S11', 'period_end': '2025-12-31', 'source_cik': cik,
        'source_file_sha256': sha256(raw).hexdigest(),
        'source_filing_accession': prior['target']['form_accession'],
        'source_10k_header_sha256': prior['target']['header_sha256'],
        'companyfacts_sha256': prior['target_financial_companyfacts_sha256'],
        'industry_sic': '2834', 'eligible_peer_count': 20,
        'source_accepted_at': prior['target']['accepted_at'],
        'as_of': at.astimezone(timezone.utc).isoformat(),
        'discretionary_accrual': da,
        'original_OLS_evidence_hash': prior['s11_result_evidence_hash'],
        'components': prior['s11_components'],
        'independent_decimal_reference': prior['independent_decimal_reference'],
        'independent_confirmed': True,
        'original_source_bytes_replayed': True,
        'historical_pit_accepted': False, 'canonical_accepted': False,
        'cache_path': str(cache.resolve()),
        'private_receipt_path': str(receipt.resolve()),
        'runtime_path': str(runtime.resolve()),
    }


def verify_eton_jones_receipt(receipt: Path, *, cache: Path, runtime: Path) -> dict:
    return _verify_calendar_receipt(receipt, cache=cache, runtime=runtime,
                                    ticker='ETON')


def verify_crmd_jones_receipt(receipt: Path, *, cache: Path, runtime: Path) -> dict:
    return _verify_calendar_receipt(receipt, cache=cache, runtime=runtime,
                                    ticker='CRMD')
