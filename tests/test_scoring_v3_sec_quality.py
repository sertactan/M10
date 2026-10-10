"""Synthetic SEC accounting matrix: validates exact source and research gates."""
import json
import unittest
from decimal import Decimal
from app.scoring_v3_sec_quality import ACCESSIONS,TAGS,INSTANT,recover
from scripts.scoring_v3_quality_probe import verify_presentation


def fixture():
    values={
        2023:dict(revenue=100,direct_cost=60,gross_profit=40,
                  accounts_receivable=10,current_assets=35,ppe_net=20,total_assets=100,
                  sga=20,net_income=5,operating_cash_flow=5,cash=10),
        2024:dict(revenue=160,direct_cost=100,gross_profit=60,
                  accounts_receivable=20,current_assets=40,ppe_net=25,total_assets=120,
                  sga=22,net_income=10,operating_cash_flow=11,cash=12),
        2025:dict(revenue=250,direct_cost=150,gross_profit=100,
                  accounts_receivable=30,current_assets=50,ppe_net=30,total_assets=150,
                  sga=28,net_income=12,operating_cash_flow=14,cash=15),
    }
    facts={'cik':903651,'facts':{'us-gaap':{}}}
    filing_dates={2023:'2025-02-24',2024:'2026-02-26',2025:'2026-02-26'}
    for y, data in values.items():
        for field,value in data.items():
            tag=TAGS[field]
            concept=facts['facts']['us-gaap'].setdefault(tag,{'units':{'USD':[]}})
            r={'accn':ACCESSIONS[y],'form':'10-K','end':f'{y}-12-31',
               'filed':filing_dates[y],'val':value}
            if field not in INSTANT:
                r['start']=f'{y}-01-01'
            concept['units']['USD'].append(r)
    filings=[(ACCESSIONS[2025],'2026-02-26','2026-02-26T22:22:13Z','2025-12-31'),
             (ACCESSIONS[2023],'2025-02-24','2025-02-24T19:09:04Z','2024-12-31')]
    subs={'cik':903651,'filings':{'recent':{
        'accessionNumber':[f[0] for f in filings],
        'filingDate':[f[1] for f in filings],
        'acceptanceDateTime':[f[2] for f in filings],
        'reportDate':[f[3] for f in filings],
        'form':['10-K','10-K']}}}
    return json.dumps(facts).encode(),json.dumps(subs).encode()


class SecV3Tests(unittest.TestCase):
    def test_five_risk_legs_require_gross_profit_filing_presentation(self):
        raw,sub=fixture()
        p=recover(raw,sub,retrieved_at='2026-10-11T00:00:00Z')
        self.assertEqual(p['beneish']['verified_risk_count'],4)
        self.assertIsNone(p['beneish']['risk_components']['GMI'])
        self.assertIsNone(p['beneish']['B_Q_SCORE'])
        self.assertEqual(p['dechow']['partial_input_count'],4)
        self.assertIsNone(p['dechow']['S6_SCORE'])
        self.assertEqual(p['beneish']['ratios']['GMI'],float((Decimal(60)/160)/(Decimal(100)/250)))
        self.assertAlmostEqual(p['dechow']['verified_partial']['DELTA_REC'],10/135)
        self.assertAlmostEqual(p['dechow']['verified_partial']['DELTA_CASHSALES'],(240-150)/150)
        review={'verified':True,'10k_accession':ACCESSIONS[2025],
                'document_sha256':'ab'*32,'scope':'CONSOLIDATED_GAAP_STATEMENT_OF_OPERATIONS',
                'direct_operating_cost_is_gross_profit_cost':True,
                'source_ref':'https://www.sec.gov/Archives/edgar/data/903651/000110465926020655/inod-20251231x10k.htm'}
        x=recover(raw,sub,retrieved_at='2026-10-11T00:00:00Z',presentation_review=review)
        self.assertEqual(x['beneish']['verified_risk_count'],5)
        self.assertEqual(x['beneish']['risk_components']['GMI'],0)
        self.assertIsNone(x['S14_SCORE'])

    def test_inconsistent_gross_profit_rejected(self):
        raw,sub=fixture();payload=json.loads(raw)
        payload['facts']['us-gaap']['GrossProfit']['units']['USD'][-1]['val']=77
        with self.assertRaisesRegex(ValueError,'gross profit'):
            recover(json.dumps(payload).encode(),sub,retrieved_at='2026-10-11T00:00:00Z')

    def test_filing_scope_and_future_access_block(self):
        raw,sub=fixture();s=json.loads(sub)
        s['cik']=1
        with self.assertRaisesRegex(ValueError,'issuer'):
            recover(raw,json.dumps(s).encode(),retrieved_at='2026-10-11T00:00:00Z')
        with self.assertRaisesRegex(ValueError,'annual accession'):
            recover(raw,sub,retrieved_at='2025-01-01T00:00:00Z')

    def test_filing_body_attestation_requires_consolidated_statement(self):
        raw,sub=fixture()
        forged=b'<html>unknown statement Direct operating costs 150 100</html>'
        self.assertFalse(verify_presentation(forged,raw,sub)['verified'])
        body=b'''<html>INNODATA INC <h1>CONSOLIDATED STATEMENTS OF OPERATIONS AND COMPREHENSIVE INCOME</h1>
            YEARS ENDED DECEMBER 31 2025 AND 2024 (In thousands)
            Revenues 250 160 Direct operating costs 150 100 Gross Profit 100 60
            </html>'''
        self.assertTrue(verify_presentation(body,raw,sub)['verified'])


if __name__=='__main__':
    unittest.main()
