"""Replay S6 RSST from existing SEC bytes, writing only a new private receipt."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.scoring_v4_dechow import audit_rsst


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--companyfacts-zip', type=Path, required=True)
    parser.add_argument('--filing-cache', type=Path, required=True)
    parser.add_argument('--model-source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if '.scoring_v4_private' not in output.parts or output.name != 'rsst_v4.json':
        raise ValueError('PRIVATE_V4_RSST_OUTPUT_REQUIRED')
    if output.exists() or Path(str(output)+'.sha256').exists():
        raise ValueError('NEW_OUTPUT_REQUIRED')
    with zipfile.ZipFile(args.companyfacts_zip) as archive:
        companyfacts = archive.read('CIK0000903651.json')
    filenames = {2024:'000141057825000194_inod-20241231x10k.htm',
                 2025:'000110465926020655_inod-20251231x10k.htm'}
    bodies = {year:(args.filing_cache/name).read_bytes() for year,name in filenames.items()}
    result = audit_rsst(companyfacts, args.model_source.read_bytes(), bodies)
    raw = (json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)+'\n').encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream:
        stream.write(raw)
    with Path(str(output)+'.sha256').open('x', encoding='ascii') as stream:
        stream.write(sha256(raw).hexdigest()+'\n')
    print(json.dumps({'rsst':result['RSST_decimal'], 'S6':result['S6'],
                      'frozen_accepted':result['RSST_frozen_accepted'],
                      'sha256':sha256(raw).hexdigest()}, sort_keys=True))


if __name__ == '__main__':
    main()
