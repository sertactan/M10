"""Write a sealed private V5 partition boundary from pinned SEC source bytes."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.scoring_v5_dechow import audit_partitions


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--companyfacts-zip', type=Path, required=True)
    p.add_argument('--filing-cache', type=Path, required=True)
    p.add_argument('--model-source', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    out = a.output.resolve()
    private_root = Path('E:/M10/.scoring_v5_private').resolve()
    if out.name != 'rsst_partitions_v5.json' or out.parent != private_root/'s6':
        raise ValueError('PRIVATE_V5_OUTPUT_REQUIRED')
    if out.exists() or Path(str(out)+'.sha256').exists():
        raise ValueError('NEW_OUTPUT_REQUIRED')
    with zipfile.ZipFile(a.companyfacts_zip) as z:
        companyfacts = z.read('CIK0000903651.json')
    names = {2024: '000141057825000194_inod-20241231x10k.htm',
             2025: '000110465926020655_inod-20251231x10k.htm'}
    bodies = {year: (a.filing_cache/name).read_bytes() for year, name in names.items()}
    result = audit_partitions(companyfacts, a.model_source.read_bytes(), bodies)
    raw = (json.dumps(result, indent=2, sort_keys=True, allow_nan=False)+'\n').encode()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('xb') as stream:
        stream.write(raw)
    with Path(str(out)+'.sha256').open('x', encoding='ascii') as stream:
        stream.write(sha256(raw).hexdigest()+'\n')
    print(json.dumps({'status': result['status'], 'S6': result['S6'],
                      'sha256': sha256(raw).hexdigest()}, sort_keys=True))


if __name__ == '__main__':
    main()
