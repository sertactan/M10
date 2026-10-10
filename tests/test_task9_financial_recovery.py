"""Source-gated real-feature math, using *synthetic* SEC fixture bytes."""
import json
import unittest

from app.task9_financial_recovery import (
    STOCK_OPTION_VALUE, _equity_statement, _no_credit_use,
    _ppe_depreciation, _extension_obligations, recover_task9_evidence,
)
from app.scoring_v3_sec_filing_evidence import _extract_text
from tests.test_scoring_v3_sec_quality import fixture


def _fixtures():
    raw, sub=fixture()
    facts=json.loads(raw)
    arr=[]
    for y,acc,amount,filing in (
        (2023,'0001410578-25-000194',3324000,'2025-02-24'),
        (2024,'0001104659-26-020655',6668000,'2026-02-26'),
        (2025,'0001104659-26-020655',3331000,'2026-02-26')):
        arr.append({'accn':acc,'form':'10-K','end':f'{y}-12-31',
                    'start':f'{y}-01-01','val':amount,'filed':filing})
    facts['facts']['us-gaap'][STOCK_OPTION_VALUE]={'units':{'USD':arr}}
    def document(year):
        nums='Stock option exercises 2024 6,668; Stock option exercises 2023 3,324' if year==2024 else 'Stock option exercises 2024 6,668; Stock option exercises 2025 3,331'
        text=('''<html><body><p>Financial statements notes and audited equity</p>
          <h2>CONSOLIDATED STATEMENTS OF STOCKHOLDERS EQUITY</h2>
          <p>'''+nums+'''</p><p>'''+('Audited stockholders equity details. '*40)+'''</p>
          <p>F-6 Table of Contents</p><h2>3. Property and equipment</h2>
          <p>Depreciation and amortization expense of property and equipment were approximately
          $2.2 million and $1.5 million for the years ended December 31, 2025 and 2024, respectively.</p>
          <h2>4. Goodwill and Intangible Assets</h2><h2>16. Line of Credit</h2>
          <p>Credit agreement was not used. The Company did not utilize the Revolving Credit Facility
          during the year ended December 31, '''+str(year)+''' or during the subsequent period through filing.</p>
          </body></html>''')
        return text.encode()
    return json.dumps(facts).encode(),sub,{2024:document(2024),2025:document(2025)}


class Task9FinanceTests(unittest.TestCase):
    def test_issuance_is_real_equity_option_exercise_not_sbc(self):
        raw, sub, bodies=_fixtures()
        r=recover_task9_evidence(raw,sub,bodies,retrieved_at='2026-10-10T18:33:11Z')
        self.assertEqual([r['issuance'][y]['indicator'] for y in (2023,2024,2025)],[1,1,1])
        self.assertEqual(r['issuance'][2025]['amount_usd'],3331000)
        self.assertEqual(r['S6_ISSUE'],1)
        self.assertEqual(r['S6_total_verified_components'],5)
        self.assertIsNone(r['S6'])
        self.assertIsNone(r['B_Q'])
        self.assertIsNone(r['S14'])
        self.assertIsNone(r['RSST']['value'])
        self.assertIsNone(r['inventory']['delta_inventory'])

    def test_empty_issuance_is_not_zero_issuance(self):
        raw,sub,bodies=_fixtures()
        obj=json.loads(raw)
        del obj['facts']['us-gaap'][STOCK_OPTION_VALUE]
        r=recover_task9_evidence(json.dumps(obj).encode(),sub,bodies,
                                 retrieved_at='2026-10-10T18:33:11Z')
        self.assertIsNone(r['S6_ISSUE'])
        self.assertEqual(r['S6_total_verified_components'],4)
        self.assertIsNone(r['issuance'][2025]['indicator'])

    def test_nonmatching_statement_cannot_prove_issuance(self):
        raw,sub,bodies=_fixtures()
        bodies[2025]=bodies[2025].replace(b'Stock option exercises',b'Stock based compensation')
        r=recover_task9_evidence(raw,sub,bodies,retrieved_at='2026-10-10T18:33:11Z')
        self.assertIsNone(r['S6_ISSUE'])
        self.assertEqual(r['S6_total_verified_components'],4)

    def test_wrong_fiscal_issuer_or_filing_clock_fails(self):
        raw,sub,bodies=_fixtures()
        with self.assertRaisesRegex(ValueError,'SEC_ANNUAL_FILING_ACCEPTANCE'):
            recover_task9_evidence(raw,sub,bodies,retrieved_at='2023-01-01T00:00:00Z')
        obj=json.loads(raw);obj['cik']=1
        with self.assertRaisesRegex(ValueError,'CIK'):
            recover_task9_evidence(json.dumps(obj).encode(),sub,bodies,
                                  retrieved_at='2026-10-10T18:33:11Z')

    def test_no_unused_facility_inflated_to_total_debt(self):
        raw,sub,bodies=_fixtures()
        r=recover_task9_evidence(raw,sub,bodies,retrieved_at='2026-10-10T18:33:11Z')
        self.assertEqual(r['credit_facility'][2024]['facility_usage'],0)
        self.assertEqual(r['credit_facility'][2025]['facility_usage'],0)
        self.assertIsNone(r['credit_facility'][2025]['total_interest_bearing_debt'])
        self.assertIsNone(r['credit_facility'][2025]['LVGI'])
        self.assertIsNone(r['ppe_depreciation'][2025]['DEPI'])
        self.assertEqual(r['ppe_depreciation'][2025]['PPE_depreciation_and_amortization_million_approx'],[2.2,1.5])

    def test_inline_extension_pension_is_not_interest_bearing_debt(self):
        raw,sub,bodies=_fixtures()
        amounts={2024:{'current':1643,'noncurrent':6744,'total':8387,'software_license':442},
                 2025:{'current':1659,'noncurrent':7625,'total':9284,'software_license':6}}
        from app.task9_financial_recovery import OBLIGATION_EXTENSION
        tags=[]
        for y,components in amounts.items():
            for name,amount in components.items():
                tags.append(f'<ix:nonFraction name="{OBLIGATION_EXTENSION[name]}" '
                            f'contextRef="As_Of_12_31_{y}_sample" unitRef="Unit_USD" '
                            f'scale="3">{amount:,}</ix:nonFraction>')
        note=('''<h2>6. Long-term obligations</h2><p>Total long-term obligations
        Pension obligations - accrued pension liability $9,278 $7,945
        Microsoft licenses (1) $6 $442 9,284 8,387</p>
        <h2>7. Commitments and contingencies</h2>''')
        body=bodies[2025].replace(b'</body>',(note+''.join(tags)).encode()+b'</body>')
        parsed=_extension_obligations(body,_extract_text(body),(2024,2025))
        self.assertEqual(parsed[2024]['status'],'SOURCE_RECONCILED_MIXED_OBLIGATIONS')
        self.assertEqual(parsed[2025]['amounts_usd']['pension_obligation'],9278000)
        self.assertEqual(parsed[2025]['amounts_usd']['software_license_obligation'],6000)
        self.assertEqual(parsed[2025]['amounts_usd']['total_long_term_obligations'],9284000)
        self.assertIsNone(parsed[2025]['separately_proven_interest_bearing_debt'])
        self.assertIsNone(parsed[2025]['LVGI'])


if __name__=='__main__':unittest.main()
