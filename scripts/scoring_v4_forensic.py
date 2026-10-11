"""Replay all cached SEC filings and save an unsigned private S13 review packet."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.scoring_v4_forensic import build_packet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--filing-cache', type=Path, required=True)
    parser.add_argument('--model-source', type=Path, required=True)
    parser.add_argument('--proxy-pdf', type=Path, required=True)
    parser.add_argument('--proxy-text', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--as-of', required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if '.scoring_v4_private' not in output.parts or output.name != 'review_v4.json':
        raise ValueError('PRIVATE_V4_FORENSIC_OUTPUT_REQUIRED')
    if output.exists() or Path(str(output)+'.sha256').exists():
        raise ValueError('NEW_OUTPUT_REQUIRED')
    prior_raw = args.baseline.read_bytes()
    prior = json.loads(prior_raw)
    sources = {}
    all_bodies = {}
    for path in sorted(args.filing_cache.glob('*.htm.receipt.json')):
        if path.is_symlink(): raise ValueError('SYMLINK_RECEIPT_REJECTED')
        receipt = json.loads(path.read_text(encoding='utf8'))
        body_path = path.with_name(path.name.removesuffix('.receipt.json'))
        if body_path.is_symlink(): raise ValueError('SYMLINK_BODY_REJECTED')
        body = body_path.read_bytes()
        if sha256(body).hexdigest() != receipt.get('sha256'):
            raise ValueError('FILING_BODY_HASH_CHANGED')
        accession = receipt['accession']
        if accession in all_bodies: raise ValueError('DUPLICATE_ACCESSION')
        all_bodies[accession] = receipt['sha256']
    if len(all_bodies) != 14:
        raise ValueError('EXPECTED_14_ORIGINAL_SEC_DOCUMENTS')
    for block in prior['blocks'].values():
        for finding in block['findings']:
            acc = finding['accession']
            if acc in sources: continue
            paths = list(args.filing_cache.glob(acc.replace('-','')+'*.htm'))
            if len(paths) != 1 or acc not in all_bodies:
                raise ValueError('FINDING_SOURCE_BODY_MISSING')
            sources[acc] = ({'source_content_sha256':finding['filing_body_sha256'],
                             'extracted_text_sha256':finding['extracted_text_sha256'],
                             'source_ref':finding['source_ref']}, paths[0].read_bytes())
    report = build_packet(prior_raw, sources, args.model_source.read_bytes(),
                          proxy_pdf=args.proxy_pdf.read_bytes(),
                          proxy_text=args.proxy_text.read_text(encoding='utf8'),
                          as_of=args.as_of)
    report['all_14_official_body_sha256'] = all_bodies
    raw = (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)+'\n').encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream:
        stream.write(raw)
    with Path(str(output)+'.sha256').open('x', encoding='ascii') as stream:
        stream.write(sha256(raw).hexdigest()+'\n')
    print(json.dumps({'findings':report['preserved_findings_verified'],
                      'SEC_bodies':len(all_bodies), 'risk_decisions':report['completed_risk_decisions'],
                      'S13':report['S13'], 'sha256':sha256(raw).hexdigest()}))


if __name__ == '__main__':
    main()
