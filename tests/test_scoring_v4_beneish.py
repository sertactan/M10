from decimal import Decimal
from hashlib import sha256
import json

import pytest

from app.scoring_v4_beneish import InlineEvidence, decimal_ratios, parse_verified, replay


def test_inline_dimensional_amortization_is_not_consolidated_depreciation():
    p = InlineEvidence()
    p.feed('''<xbrli:context id="software"><xbrli:entity><xbrldi:explicitMember
        dimension="us-gaap:FiniteLivedIntangibleAssetsByMajorClassAxis">us-gaap:ComputerSoftwareIntangibleAssetMember</xbrldi:explicitMember></xbrli:entity>
        <xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate><xbrli:endDate>2025-12-31</xbrli:endDate></xbrli:period></xbrli:context>
        <xbrli:unit id="USD"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
        <ix:nonFraction name="us-gaap:AmortizationOfIntangibleAssets" contextRef="software"
        unitRef="USD" scale="6" decimals="-5">4.0</ix:nonFraction>''')
    assert p.facts[0]['value'] == '4000000.0'
    assert 'ComputerSoftwareIntangibleAssetMember' in p.contexts['software']['markup']
    assert '2025-01-01' in p.contexts['software']['markup']
    assert p.units['USD']['text'] == 'iso4217:USD'


def inputs(**changes):
    result = dict(dep_prior=10, dep_current=12, ppe_prior=100, ppe_current=110,
                  debt_prior=20, debt_current=22, assets_prior=200, assets_current=250)
    result.update(changes)
    return result


def test_decimal_reference_matches_independent_cross_products():
    r = decimal_ratios(**inputs())
    assert float(r['DEPI']['value']) == pytest.approx((10*122)/(110*12))
    assert Decimal(r['LVGI']['value']) == Decimal('0.88')


@pytest.mark.parametrize('change,key,status', [
    ({'dep_current': None}, 'DEPI', 'DATA_MISSING'),
    ({'debt_prior': None}, 'LVGI', 'DATA_MISSING'),
    ({'debt_prior': 0}, 'LVGI', 'UNDEFINED_ZERO_DENOMINATOR'),
    ({'dep_current': 0}, 'DEPI', 'UNDEFINED_ZERO_DENOMINATOR'),
    ({'assets_current': 0}, 'LVGI', 'UNDEFINED_ZERO_DENOMINATOR'),
    ({'debt_current': -1}, 'LVGI', 'INVALID_INPUT'),
    ({'dep_current': 'NaN'}, 'DEPI', 'INVALID_INPUT'),
])
def test_no_epsilon_or_missing_to_zero(change, key, status):
    result = decimal_ratios(**inputs(**change))[key]
    assert result == {'value': None, 'status': status}


def test_hash_failure_rejects_source_and_baseline():
    with pytest.raises(ValueError, match='SHA-256'):
        parse_verified(b'changed', {'sha256': '0'*64})
    with pytest.raises(ValueError, match='SHA-256'):
        replay([], b'changed', '0'*64)


def test_replay_preserves_prior_zero_risk_and_never_promotes_candidate():
    prior = {'beneish': {'verified_risk_count': 5, 'ratios': {'GMI': 0.995, 'SGI': 1.476}}}
    baseline = json.dumps(prior).encode()
    body = b'<ix:nonFraction name="us-gaap:DepreciationDepletionAndAmortization" scale="6">2.2</ix:nonFraction>'
    receipt = dict(sha256=sha256(body).hexdigest(), form='10-K', accession='test',
                   source_ref='https://www.sec.gov/Archives/edgar/data/903651/test.htm')
    result = replay([(body, receipt)], baseline, sha256(baseline).hexdigest())
    assert result['B_Q'] is None
    assert result['preserved_ratios'] == prior['beneish']['ratios']
    assert result['verified_risk_count'] == 5
    assert result['sources'][0]['candidate_facts'][0]['value'] == '2200000.0'
    assert result['sources'][0]['source_authenticity_independently_verified'] is False
