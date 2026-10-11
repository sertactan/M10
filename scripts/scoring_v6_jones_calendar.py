"""Bounded FY2025 SEC Jones cohorts; sealed private reports."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.task9_jones_cohort import SECCache, read_sec_contact, scan_task9


PRIVATE = Path('E:/M10/.scoring_v6_private').resolve()
TARGETS = {
    'CRMD': ('0001410098', '2834', 8, 'task9_jones_eton', 'Revenues', '2025-12-31'),
    'TMDX': ('0001756262', '3845', 10, 'task9_jones_tmdx', 'Revenues', '2025-12-31'),
    'PENG': ('0001616533', '3674', 12, 'task9_jones_peng',
             'RevenueFromContractWithCustomerExcludingAssessedTax', '2025-08-29'),
}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('ticker', choices=TARGETS)
    p.add_argument('--budget', type=int, default=100)
    p.add_argument('--max-candidates', type=int, default=80)
    a = p.parse_args()
    if not (0 <= a.budget <= 120 and 20 <= a.max_candidates <= 100):
        raise ValueError('BOUNDED_SEC_REQUESTS_REQUIRED')
    cik, sic, pages, cache_name, revenue_tag, anchor_end = TARGETS[a.ticker]
    out = PRIVATE/('jones_'+a.ticker.lower())/'report.json'
    seal = Path(str(out)+'.sha256')
    if out.exists() or seal.exists():
        raise ValueError('NEW_PRIVATE_REPORT_REQUIRED')
    contact = read_sec_contact(Path('E:/M10/.env'))
    if not contact:
        raise ValueError('CONFIGURED_LEGITIMATE_SEC_CONTACT_REQUIRED')
    cache = SECCache(PRIVATE/cache_name, contact=contact, request_budget=a.budget)
    runtime = Path(os.environ['LOCALAPPDATA'])/'S153ResearchTerminal'/'runtime'
    result = scan_task9(cache, runtime=runtime, max_pages=pages,
                        max_candidates=a.max_candidates, target_cik=cik,
                        target_ticker=a.ticker, sic=sic,
                        target_revenue_tag=revenue_tag, anchor_end=anchor_end)
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(result, ensure_ascii=False, indent=2,
                      sort_keys=True, allow_nan=False)+'\n').encode()
    with out.open('xb') as stream:
        stream.write(raw)
    with seal.open('x', encoding='ascii') as stream:
        stream.write(sha256(raw).hexdigest()+'\n')
    print(json.dumps({'ticker': a.ticker, 'status': result['status'],
                      'S11': result['s11_score'],
                      'peers': result['verified_same_sic_independent_peers'],
                      'precheck_8_of_8': result['precheck_8_of_8'],
                      'missing': result['s11_missing'],
                      'stop': result['stop_reason'],
                      'requests': result['network_requests'],
                      'http_statuses': result['http_statuses'],
                      'receipt_sha256': sha256(raw).hexdigest()}, sort_keys=True))


if __name__ == '__main__':
    main()
