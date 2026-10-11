"""Unsigned expert decision form from a hash-sealed S13 evidence packet."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path


BLOCKS = ("AUD", "RPT", "REC", "DIL", "REV", "ACQ", "GOV")


def unsigned_form(packet_path: Path) -> dict:
    packet_path = Path(packet_path)
    raw = packet_path.read_bytes()
    seal = Path(str(packet_path) + '.sha256').read_text(encoding='ascii').strip()
    if sha256(raw).hexdigest() != seal:
        raise ValueError('V4_FORENSIC_PACKET_SEAL_CHANGED')
    packet = json.loads(raw)
    issuer = packet.get('issuer')
    if (not isinstance(issuer, dict) or issuer.get('ticker') != 'INOD'
            or issuer.get('cik') != '0000903651'
            or packet.get('preserved_findings_verified') != 27):
        raise ValueError('UNEXPECTED_FORENSIC_PACKET')
    if set(packet['blocks']) != set(BLOCKS) or packet.get('completed_risk_decisions') != 0:
        raise ValueError('FORENSIC_DECISION_STATE_CHANGED')
    blocks = {}
    for name in BLOCKS:
        item = packet['blocks'][name]
        findings = item['preserved_findings']
        if any(f.get('block') != name or not f.get('source_ref') or
               len(f.get('filing_body_sha256', '')) != 64 for f in findings):
            raise ValueError('FINDING_SOURCE_INCOMPLETE')
        blocks[name] = {
            'source_findings': [{k: f[k] for k in ('finding_id', 'accession',
                'section_reference', 'source_ref', 'filing_body_sha256',
                'kind', 'observed_claim', 'inference_boundary')}
                for f in findings],
            'mitigating_and_adverse_context': item['assessment'],
            'remaining_review': item['remaining_adjudication'],
            'financial_materiality_reason': None,
            'risk_level_0_25_50_75_100': None,
            'independent_serious_issue_ids': None,
            'duplicate_issue_ids_excluded': None,
            'decision_rationale': None,
            'reviewer_name': None,
            'reviewed_at': None,
            'signed': False,
        }
    return {
        'schema': 'M10_V5_S13_UNSIGNED_EXPERT_DECISION_FORM_V1',
        'issuer': 'INOD', 'source_packet_sha256': seal,
        'source_contract': packet['source_contract'],
        'blocks': blocks,
        'independent_serious_flags_final': None,
        'cross_block_duplicate_review_complete': False,
        'all_decisions_signed': False,
        'S13': None, 'S14': None, 'status': 'REVIEW_REQUIRED',
        'scope': 'CURRENT_RESEARCH_ONLY', 'canonical_accepted': False,
    }
