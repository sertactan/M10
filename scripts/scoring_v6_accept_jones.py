"""Accept a verified V6 Jones score into a new sealed Research report."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.scoring_completion import attach_v6_jones_real_score, load_report, save_report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('ticker', choices=('ETON', 'CRMD'))
    p.add_argument('--input-report', type=Path, required=True)
    p.add_argument('--phase27', type=Path, required=True)
    p.add_argument('--phase28', type=Path, required=True)
    p.add_argument('--jones-receipt', type=Path, required=True)
    p.add_argument('--jones-cache', type=Path, required=True)
    p.add_argument('--runtime', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    expected = Path('E:/M10/.scoring_v6_private/scoring_completion')/(
        a.ticker.lower()+'_s11')/'report.json'
    if a.output.resolve() != expected.resolve():
        raise ValueError('NEW_PRIVATE_V6_REPORT_REQUIRED')
    report = load_report(a.input_report, a.phase27, a.phase28)
    if report['full_model_count'] != (10 if a.ticker=='ETON' else 11):
        raise ValueError('EXPECTED_PRESERVED_RESEARCH_SCORE_BASELINE')
    attach_v6_jones_real_score(report, a.jones_receipt, a.jones_cache,
                               a.runtime, ticker=a.ticker)
    save_report(report, a.output)
    verified = load_report(a.output, a.phase27, a.phase28)
    stock = next(s for s in verified['stocks'] if s['ticker']==a.ticker)
    model14 = next(m for m in stock['models'] if m['model']=='S14')
    print(json.dumps({'status': 'REAL_SCORE_ACCEPTED_RESEARCH',
                      'ticker': a.ticker, 'S11': stock['quality']['S11']['score'],
                      'S14': model14['score'], 'S14_coverage': model14['present'],
                      'full_research_scores': verified['full_model_count'],
                      'canonical_securities': verified['canonical_securities']}))


if __name__ == '__main__':
    main()
