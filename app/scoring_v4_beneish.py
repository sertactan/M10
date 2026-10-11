"""Offline, hash-bound Beneish evidence replay; never infer missing debt or depreciation."""
from __future__ import annotations

from decimal import Decimal, localcontext
from hashlib import sha256
from html.parser import HTMLParser
import json
import re


class InlineEvidence(HTMLParser):
    """Capture inline facts and full context/unit XML without optional dependencies."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.active = []
        self.facts = []
        self.contexts = {}
        self.units = {}
        self.parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        for item in self.active:
            item['markup'].append(self.get_starttag_text())
        if tag in ('ix:nonfraction', 'xbrli:context', 'xbrli:unit'):
            self.active.append({'tag': tag, 'attrs': attrs, 'text': [], 'markup': []})

    def handle_data(self, data):
        self.parts.append(data)
        for item in self.active:
            item['text'].append(data)
            item['markup'].append(data)

    def handle_endtag(self, tag):
        for item in self.active:
            item['markup'].append(f'</{tag}>')
        if not self.active or self.active[-1]['tag'] != tag:
            return
        item = self.active.pop()
        attrs = item['attrs']
        raw = ''.join(item['text']).strip()
        if tag == 'ix:nonfraction':
            record = dict(attrs, raw=raw)
            try:
                number = raw.replace(',', '').replace(' ', '').replace('\u00a0', '')
                # A presentation dash is not a source-certified numeric zero.
                # Keep it unavailable even in the research candidate inventory.
                if number in ('—', '–', '-'):
                    raise ValueError('NONNUMERIC_PRESENTATION_DASH')
                value = Decimal(number) * Decimal(10) ** int(attrs.get('scale', '0'))
                if attrs.get('sign') == '-':
                    value = -value
                record['value'] = str(value)
            except (ValueError, ArithmeticError):
                record['value'] = None
            self.facts.append(record)
        else:
            target = self.contexts if tag == 'xbrli:context' else self.units
            target[attrs.get('id')] = {'text': raw, 'markup': ''.join(item['markup'])}

    @property
    def text(self):
        return re.sub(r'\s+', ' ', ' '.join(self.parts).replace('\u200b', '')).strip()


def parse_verified(body: bytes, receipt: dict) -> InlineEvidence:
    if sha256(body).hexdigest() != receipt.get('sha256'):
        raise ValueError('Filing body SHA-256 mismatch')
    if receipt.get('form') != '10-K' or not receipt.get('source_ref', '').startswith(
        'https://www.sec.gov/Archives/edgar/data/903651/'
    ):
        raise ValueError('Expected INOD annual SEC source receipt')
    parser = InlineEvidence()
    parser.feed(body.decode('utf-8'))
    return parser


def decimal_ratios(*, dep_prior, dep_current, ppe_prior, ppe_current,
                   debt_prior, debt_current, assets_prior, assets_current):
    """Independent frozen DEPI/LVGI reference, preserving missing and zero distinction."""
    result = {}
    with localcontext() as ctx:
        ctx.prec = 50
        for name, values in {
            'DEPI': (dep_prior, dep_current, ppe_prior, ppe_current),
            'LVGI': (debt_prior, debt_current, assets_prior, assets_current),
        }.items():
            if any(v is None for v in values):
                result[name] = {'value': None, 'status': 'DATA_MISSING'}
                continue
            a, b, c, d = map(lambda v: Decimal(str(v)), values)
            if not all(v.is_finite() for v in (a, b, c, d)) or min(a, b, c, d) < 0:
                result[name] = {'value': None, 'status': 'INVALID_INPUT'}
                continue
            denominators = (a + c, b + d, b) if name == 'DEPI' else (c, d, a)
            if min(denominators) <= 0:
                result[name] = {'value': None, 'status': 'UNDEFINED_ZERO_DENOMINATOR'}
                continue
            val = (a / (a + c)) / (b / (b + d)) if name == 'DEPI' else (b / d) / (a / c)
            result[name] = {'value': str(val), 'status': 'CALCULATED_REFERENCE_ONLY'}
    return result


SEARCH_TERMS = ('depreciation and amortization expense', 'amortization expense',
                'software licenses', 'Microsoft licenses', 'interest paid',
                'interest expense', 'unused', 'did not utilize', 'commitment fee',
                'capitalized software', 'finance lease', 'vendor agreement')


def _annual_fact(parser, name, year, member=None):
    """Select exact annual USD facts; dimensional and consolidated scope never mix."""
    selected = []
    for fact in parser.facts:
        context = parser.contexts.get(fact.get('contextref'), {}).get('markup', '')
        unit = parser.units.get(fact.get('unitref'), {}).get('text', '')
        if fact.get('name') != name or unit != 'iso4217:USD' or fact['value'] is None:
            continue
        if f'>{year}-01-01<' not in context or f'>{year}-12-31<' not in context:
            continue
        dimensional = 'explicitmember' in context.lower() or 'typedmember' in context.lower()
        if (member is None and dimensional) or (member is not None and f'>{member}<' not in context):
            continue
        selected.append(fact)
    if len({(f['value'], f.get('decimals')) for f in selected}) != 1:
        return None
    return selected[0]


def depreciation_residual_diagnostic(parser):
    """Replay the rejected residual route with reported precision, never return DEP."""
    result = {}
    for year in (2024, 2025):
        total = _annual_fact(parser, 'us-gaap:DepreciationDepletionAndAmortization', year)
        acquired = _annual_fact(parser, 'us-gaap:AmortizationOfIntangibleAssets', year,
                                'inod:AcquiredIntangibleAssetsMember')
        software = _annual_fact(parser, 'us-gaap:AmortizationOfIntangibleAssets', year,
                                'us-gaap:ComputerSoftwareIntangibleAssetMember')
        if not all((total, acquired, software)):
            result[str(year)] = {'status': 'RESIDUAL_INPUT_MISSING', 'depreciation': None}
            continue
        values = [Decimal(f['value']) for f in (total, acquired, software)]
        midpoint = values[0]-values[1]-values[2]
        # XBRL decimals describes rounding accuracy, not an exact dollar balance.
        error = sum(Decimal(10) ** -int(f['decimals']) / 2
                    for f in (total, acquired, software))
        result[str(year)] = {'status': 'REJECTED_AS_PURE_DEPRECIATION', 'depreciation': None,
                            'unit': 'USD', 'residual_midpoint': str(midpoint),
                            'rounding_interval': [str(midpoint-error), str(midpoint+error)],
                            'reason': 'Residual remains PPE depreciation AND amortization; '
                                      'PPE includes computer software and leasehold improvements.',
                            'source_facts': [total, acquired, software]}
    return result


def replay(documents: list[tuple[bytes, dict]], baseline: bytes, baseline_sha256: str) -> dict:
    """Produce auditable candidate facts/snippets while preserving sealed accepted ratios.

    Completeness of text search is not completeness of debt classification. No
    search result, extension name or combined D&A is promoted into a score.
    """
    if sha256(baseline).hexdigest() != baseline_sha256:
        raise ValueError('Prior accepted ratio receipt SHA-256 mismatch')
    prior = json.loads(baseline)['beneish']
    sources = []
    for body, receipt in documents:
        p = parse_verified(body, receipt)
        facts = []
        for fact in p.facts:
            if re.search(r'depreciation|amortization|software|interest|debt|obligation',
                         fact.get('name', ''), re.I):
                facts.append(dict(fact, context=p.contexts.get(fact.get('contextref')),
                                  unit=p.units.get(fact.get('unitref'))))
        snippets = []
        for term in SEARCH_TERMS:
            for match in re.finditer(re.escape(term), p.text, re.I):
                start, end = max(0, match.start()-200), min(len(p.text), match.end()+850)
                snippets.append({'term': term, 'start': start, 'end': end,
                                 'text': p.text[start:end]})
        sources.append({'accession': receipt['accession'], 'source_ref': receipt['source_ref'],
                        'sha256': receipt['sha256'], 'retrieved_at': receipt.get('retrieved_at'),
                        'historical_pit_accepted': False,
                        'source_authenticity_independently_verified':
                            receipt.get('source_authenticity_independently_verified', False),
                        'rejected_residual_route': depreciation_residual_diagnostic(p),
                        'candidate_facts': facts, 'contextual_evidence': snippets})
    return {'schema': 'M10_V4_BENEISH_SOURCE_REPLAY_V1', 'symbol': 'INOD',
            'period_end': '2025-12-31', 'status': 'PARTIAL_RESEARCH', 'B_Q': None,
            'verified_risk_count': prior['verified_risk_count'], 'required_risk_count': 7,
            'preserved_ratios': prior['ratios'], 'baseline_sha256': baseline_sha256,
            'sources': sources, 'missing': ['PURE_DEPRECIATION_2024_2025',
                'INTEREST_BEARING_DEBT_SCOPE_2024_2025', 'INDEPENDENT_SERIOUS_FLAGS_REVIEW'],
            'new_full_research_scores': 0, 'historical_pit_accepted': False}
