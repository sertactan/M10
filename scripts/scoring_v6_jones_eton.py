"""ETON FY2025 SIC2834 Jones cohort; private SEC cache and sealed report only."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.task9_jones_cohort import SECCache, read_sec_contact, scan_task9


PRIVATE = Path('E:/M10/.scoring_v6_private').resolve()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pages', type=int, default=8)
    p.add_argument('--budget', type=int, default=90)
    p.add_argument('--max-candidates', type=int, default=50)
    a = p.parse_args()
    if not (1 <= a.pages <= 12 and 0 <= a.budget <= 120
            and 20 <= a.max_candidates <= 100):
        raise ValueError('BOUNDED_OFFICIAL_SEC_REQUESTS_REQUIRED')
    contact = read_sec_contact(Path('E:/M10/.env'))
    if not contact:
        raise ValueError('CONFIGURED_LEGITIMATE_SEC_CONTACT_REQUIRED')
    out = PRIVATE/'jones_eton'/'report.json'
    seal = Path(str(out)+'.sha256')
    if out.exists() or seal.exists():
        raise ValueError('NEW_PRIVATE_REPORT_REQUIRED')
    runtime = Path(os.environ['LOCALAPPDATA'])/'S153ResearchTerminal'/'runtime'
    cache = SECCache(PRIVATE/'task9_jones_eton', contact=contact,
                     request_budget=a.budget)
    result = scan_task9(cache, runtime=runtime, max_pages=a.pages,
                        max_candidates=a.max_candidates,
                        target_cik='0001710340', target_ticker='ETON', sic='2834')
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(result, ensure_ascii=False, indent=2,
                      sort_keys=True, allow_nan=False)+'\n').encode()
    with out.open('xb') as stream:
        stream.write(raw)
    with seal.open('x', encoding='ascii') as stream:
        stream.write(sha256(raw).hexdigest()+'\n')
    print(json.dumps({'status': result['status'], 'S11': result['s11_score'],
                      'peers': result['verified_same_sic_independent_peers'],
                      'precheck_8_of_8': result['precheck_8_of_8'],
                      'missing': result['s11_missing'], 'stop': result['stop_reason'],
                      'requests': result['network_requests'],
                      'http_statuses': result['http_statuses'],
                      'receipt_sha256': sha256(raw).hexdigest()}, sort_keys=True))


if __name__ == '__main__':
    main()
