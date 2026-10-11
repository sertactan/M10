"""Replay preserved S13 contexts and quantify review evidence, never infer severity.

Pure offline functions. Source replay is deliberately separate from a qualified
reviewer's materiality decision; the original rubric defines no numeric cutoffs.
"""
from hashlib import sha256
import json
import re
from app.scoring_v3_sec_filing_evidence import _extract_text
from app.task9_forensic_review import SOURCE_SHA

BASELINE_SHA = 'a61cf29c59a3e0f095f29835037e08b935997e048591c1b0bc87b66b0cf38355'
PROXY_URL = 'https://d18rn0p25nwr6d.cloudfront.net/CIK-0000903651/29d67014-4d14-4039-aae2-4512a1ee9e8b.pdf'
PROXY_LANDING = 'https://investor.innodata.com/financials/sec-filings/sec-filings-details/default.aspx?FilingId=19366041'
PROXY_SEC = 'https://www.sec.gov/Archives/edgar/data/903651/000110465926048201/tm261509d1_def14a.htm'

ASSESSMENTS = {
 'AUD': ('Unmodified financial opinions mitigate; no ICFR audit opinion was issued. Revenue CAM reflects audit complexity.', 'Complete Item9A management assessment and subsequent control-event coverage; absence of a negative opinion is not proof of no risk.'),
 'RPT': ('2026 proxy supplies the missing incorporated related-party section. No Item404 reportable transaction is disclosed within its threshold/date scope.', 'Assess below-threshold and subsequent transactions, affiliate scope, and FY2024 proxy body; do not generalize disclosure absence.'),
 'REC': ('Concentration persists. The Q2 allowance roll-forward identifies recoveries, not merely a unexplained reserve release.', 'Resolve one-versus-two-customer FY2025 comparative, aging, DSO, collectability and materiality of allowances.'),
 'DIL': ('SBC expense increased; actual basic outstanding shares increased while weighted diluted shares decreased. ATM capacity is not executed issuance.', 'Review SBC/revenue and share reconciliation, exercise offsets and post-August actual sales. Frozen rubric has no high-SBC numerical threshold.'),
 'REV': ('Advance balances are liabilities; policy defers recognition. Auditor performed sample contract and receipt procedures.', 'Contract performance and estimate changes need substantive judgment; neither a CAM nor customer advances automatically establish aggressive recognition.'),
 'ACQ': ('Goodwill and intangible asset balances can be scaled to assets; management reports no impairment.', 'Assess acquisitions, organic growth and valuation assumptions; low goodwill alone does not establish zero acquisition risk.'),
 'GOV': ('SEC/DOJ requests and litigation allegations are real events, not adjudicated misconduct; succession is not inherently a control failure.', 'Verify outcomes and conflicts; potentially overlapping SEC/DOJ/class-action mentions require one underlying-issue independence review.'),
}

def flat(text):
    return re.sub(r'\s+', ' ', text).strip()

def replay_contexts(baseline_raw, sources, contract_raw):
    """Replay all 27 saved claims against unchanged filing bytes; no new scan."""
    if sha256(baseline_raw).hexdigest() != BASELINE_SHA:
        raise ValueError('BASELINE_REVIEW_CHANGED')
    if sha256(contract_raw).hexdigest() != SOURCE_SHA:
        raise ValueError('ORIGINAL_RUBRIC_CHANGED')
    prior = json.loads(baseline_raw)
    parsed = {}
    for accession, (meta, raw) in sources.items():
        if sha256(raw).hexdigest() != meta['source_content_sha256']:
            raise ValueError('BODY_CHANGED')
        text = _extract_text(raw)
        if sha256(text.encode()).hexdigest() != meta['extracted_text_sha256']:
            raise ValueError('TEXT_CHANGED')
        parsed[accession] = (meta, text)
    count = 0
    for block in prior['blocks'].values():
        for f in block['findings']:
            meta, text = parsed[f['accession']]
            if (f['filing_body_sha256'] != meta['source_content_sha256']
                    or f['source_ref'] != meta['source_ref']
                    or flat(f['context_excerpt']) not in flat(text)):
                raise ValueError('SAVED_CONTEXT_NOT_IN_SOURCE')
            count += 1
    if count != 27:
        raise ValueError('EXPECTED_27_PRESERVED_FINDINGS')
    return prior

def proxy_context(pdf_raw, extracted_text):
    """Caller must extract text from supplied PDF; script performs that binding."""
    if not pdf_raw.startswith(b'%PDF-'):
        raise ValueError('PROXY_PDF_REQUIRED')
    text = flat(extracted_text)
    anchor = 'There have been no related party transactions, as of the date hereof'
    start = text.find(anchor)
    end = text.find('EXPENSE OF SOLICITATION', start)
    if start < 0 or end <= start:
        raise ValueError('RELATED_PARTY_SECTION_MISSING')
    excerpt = text[start:end].strip()
    if not all(x in excerpt for x in ('Item 404', '$120,000', 'one percent (1%)', 'material interest')):
        raise ValueError('DISCLOSURE_THRESHOLD_CONTEXT_MISSING')
    return {'accession': '0001104659-26-048201', 'filing_date': '2026-04-24',
            'source_ref': PROXY_URL, 'issuer_link': PROXY_LANDING, 'sec_reference': PROXY_SEC,
            'body_sha256': sha256(pdf_raw).hexdigest(),
            'text_sha256': sha256(extracted_text.encode()).hexdigest(),
            'excerpt': excerpt, 'scope': 'ITEM404_DISCLOSURE_THRESHOLD_AS_OF_PROXY_DATE',
            'risk': None, 'human_review_completed': False}

def materiality_diagnostics(prior):
    """Real numbers accepted only with all associated preserved table tokens.

    These are economic magnitudes, not replacement S13 scoring thresholds.
    """
    texts = {b: ' '.join(f['context_excerpt'] for f in r['findings'])
             for b, r in prior['blocks'].items()}
    specs = (
        ('REC', 'credit_loss_allowance_pct_gross_ar_2026Q2', ('49,492', '487'), 487, 49492, '2026-06-30'),
        ('REC', 'credit_loss_allowance_pct_gross_ar_2025', ('48,606', '1,181'), 1181, 48606, '2025-12-31'),
        ('DIL', 'SBC_growth_pct_H1_2026_vs_2025', ('13,104', '5,602'), 13104-5602, 5602, 'H1_2026_vs_H1_2025'),
        ('ACQ', 'goodwill_pct_assets_2026Q2', ('2,036', '356,673'), 2036, 356673, '2026-06-30'),
        ('ACQ', 'goodwill_and_intangibles_pct_assets_2026Q2', ('2,036', '14,189', '356,673'), 2036+14189, 356673, '2026-06-30'),
        ('ACQ', 'actual_outstanding_share_growth_pct_H1_2026', ('34,376', '32,337'), 34376-32337, 32337, 'H1_2026'),
    )
    result = []
    for block, name, tokens, numerator, denominator, period in specs:
        refs = [f['finding_id'] for f in prior['blocks'][block]['findings']
                if all(token in f['context_excerpt'] for token in tokens)]
        if not refs:
            raise ValueError('MATERIALITY_INPUT_NOT_CORROBORATED:' + name)
        result.append({'name': name, 'numerator': numerator, 'denominator': denominator,
                       'percent': 100*numerator/denominator, 'period': period,
                       'finding_ids': refs, 'numeric_risk': None})
    return result

def build_packet(baseline_raw, sources, contract_raw, *, proxy_pdf, proxy_text, as_of):
    prior = replay_contexts(baseline_raw, sources, contract_raw)
    proxy = proxy_context(proxy_pdf, proxy_text)
    blocks = {}
    for block, (assessment, missing) in ASSESSMENTS.items():
        blocks[block] = {'assessment': assessment, 'remaining_adjudication': missing,
                         'preserved_findings': prior['blocks'][block]['findings'],
                         'risk': None, 'status': 'EXPERT_MATERIALITY_REVIEW_REQUIRED',
                         'human_review_completed': False, 'coverage_complete': False}
    return {'version': 'M10_SCORING_V4_FORENSIC_REPLAY_V1', 'issuer': prior['issuer'],
            'as_of': as_of, 'scope': 'CURRENT_RESEARCH_NOT_HISTORICAL_PIT',
            'source_contract': prior['source_contract'], 'baseline_sha256': BASELINE_SHA,
            'preserved_findings_verified': 27, 'filing_bodies_verified': len(sources),
            'new_proxy_context': proxy, 'blocks': blocks,
            'materiality_diagnostics': materiality_diagnostics(prior),
            'completed_risk_decisions': 0, 'S13': None, 'S14': None,
            'serious_flag_count': None, 'independence_review_complete': False,
            'status': 'REVIEW_REQUIRED', 'canonical_accepted': False,
            'reason': 'Frozen rubric has qualitative severity levels without numerical materiality thresholds. Evidence replay is not a signed risk decision.'}
