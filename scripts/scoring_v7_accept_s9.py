"""Attach the three independently replayed Piotroski S9 results to a new report."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.scoring_completion import attach_v7_s9_real_scores, load_report, save_report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input-report', type=Path, required=True)
    p.add_argument('--phase27', type=Path, required=True)
    p.add_argument('--phase28', type=Path, required=True)
    p.add_argument('--companyfacts-archive', type=Path, required=True)
    p.add_argument('--cache-root', type=Path, required=True)
    p.add_argument('--runtime', type=Path, required=True)
    p.add_argument('--receipt-root', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    expected = Path('E:/M10/.scoring_v7_private/scoring_completion/piotroski_s9/report.json')
    if a.output.resolve() != expected.resolve():
        raise ValueError('NEW_PRIVATE_V7_REPORT_REQUIRED')
    receipts = {ticker: a.receipt_root / ticker.lower() / 'report.json'
                for ticker in ('TMDX', 'PENG', 'ETON')}
    report = load_report(a.input_report, a.phase27, a.phase28)
    if report['full_model_count'] != 12:
        raise ValueError('EXPECTED_PRESERVED_V6_TWELVE_SCORE_BASELINE')
    attach_v7_s9_real_scores(report, receipts,
        companyfacts_archive=a.companyfacts_archive,
        cache_root=a.cache_root, runtime=a.runtime)
    save_report(report, a.output)
    verified = load_report(a.output, a.phase27, a.phase28)
    result = {'status': 'REAL_SCORE_ACCEPTED_RESEARCH',
              'full_research_scores': verified['full_model_count'],
              'canonical_securities': verified['canonical_securities'],
              'S9': {ticker: next(m['score'] for m in next(
                  s for s in verified['stocks'] if s['ticker'] == ticker)['models']
                  if m['model'] == 'S9') for ticker in receipts}}
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
