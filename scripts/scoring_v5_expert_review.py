"""Build a private unsigned S13 expert form; never assign risk levels."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.scoring_v5_forensic_review import unsigned_form


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--v4-packet', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    out = a.output.resolve()
    private_root = Path('E:/M10/.scoring_v5_private').resolve()
    if out.name != 's13_expert_form_v5.json' or out.parent != private_root/'s13':
        raise ValueError('PRIVATE_V5_OUTPUT_REQUIRED')
    if out.exists() or Path(str(out)+'.sha256').exists():
        raise ValueError('NEW_OUTPUT_REQUIRED')
    result = unsigned_form(a.v4_packet)
    raw = (json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True,
                      allow_nan=False)+'\n').encode()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('xb') as stream:
        stream.write(raw)
    with Path(str(out)+'.sha256').open('x', encoding='ascii') as stream:
        stream.write(sha256(raw).hexdigest()+'\n')
    print(json.dumps({'status': result['status'], 'S13': result['S13'],
                      'blocks': len(result['blocks']), 'sha256': sha256(raw).hexdigest()}))


if __name__ == '__main__':
    main()
