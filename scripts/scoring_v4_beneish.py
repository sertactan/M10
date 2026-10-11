"""Replay existing private official SEC evidence without network or live DB writes."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.scoring_v4_beneish import replay


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--filing-cache', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    filenames = ('000141057825000194_inod-20241231x10k.htm',
                 '000110465926020655_inod-20251231x10k.htm')
    documents = [(args.filing_cache.joinpath(name).read_bytes(),
                  json.loads(args.filing_cache.joinpath(name+'.receipt.json').read_bytes()))
                 for name in filenames]
    baseline = args.baseline.read_bytes()
    seal = args.baseline.with_suffix(args.baseline.suffix+'.sha256').read_text().strip().split()[0]
    report = replay(documents, baseline, seal)
    args.output.mkdir(parents=True, exist_ok=True)
    destination = args.output/'beneish_v4.json'
    encoded = (json.dumps(report, indent=2, ensure_ascii=False)+'\n').encode('utf-8')
    with destination.open('xb') as handle:
        handle.write(encoded)
    destination.with_suffix('.json.sha256').write_text(sha256(encoded).hexdigest()+'\n')
    print(json.dumps({'output': str(destination), 'sha256': sha256(encoded).hexdigest(),
                      'B_Q': report['B_Q'], 'verified_risk_count': report['verified_risk_count'],
                      'sources': len(report['sources']),
                      'candidate_facts': sum(len(s['candidate_facts']) for s in report['sources'])}))


if __name__ == '__main__':
    main()
