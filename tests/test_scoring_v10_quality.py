"""Authentic SEC-only individual model components; deliberately NO full score."""
import json, os, unittest, zipfile
from decimal import Decimal
from pathlib import Path
from app.scoring_v10_quality import depreciation_component,inod_quality_gate

class QualityRegression(unittest.TestCase):
    def test_never_replace_raw_zero_by_missing_or_guess(self):
        signed={k:{'signed':False,'risk_level_0_25_50_75_100':None}
                for k in ('AUD','RPT','REC','DIL','REV','ACQ','GOV')}
        inod={'ticker':'INOD','score_status':'REAL_SCORE_ACCEPTED_RESEARCH',
              'signals':{'F_DELTA_LEVERAGE':0},'canonical_accepted':False,
              'debt_reconciliation':{'debt_FY2025_USD':'0','debt_FY2024_USD':'0'}}
        form={'issuer':'INOD','blocks':signed,'all_decisions_signed':False}
        result=inod_quality_gate(inod,form)
        self.assertIsNone(result['B_Q_LVGI'])
        self.assertIn('0/0',result['LVGI_mathematical_case'])
        self.assertEqual(result['S13_status'],'REVIEW_REQUIRED')
        self.assertEqual(result['S6_verified_inputs'],5)
        self.assertEqual(result['S14_verified_legs'],3)
        self.assertIsNone(result['S14_score'])

    def test_no_automated_human_decision(self):
        blocks={k:{'signed':False,'risk_level_0_25_50_75_100':None}
                for k in ('AUD','RPT','REC','DIL','REV','ACQ','GOV')}
        inod={'ticker':'INOD','score_status':'REAL_SCORE_ACCEPTED_RESEARCH',
              'signals':{'F_DELTA_LEVERAGE':0},'canonical_accepted':False,
              'debt_reconciliation':{'debt_FY2025_USD':'0','debt_FY2024_USD':'0'}}
        form={'issuer':'INOD','blocks':blocks,'all_decisions_signed':False}
        blocks['AUD']['signed']=True;blocks['AUD']['risk_level_0_25_50_75_100']=0
        with self.assertRaisesRegex(ValueError,'V10_UNEXPECTED_S13_HUMAN_REVIEW_CHANGED'):
            inod_quality_gate(inod,form)

    def test_real_sec_pure_depreciation_exact_accession(self):
        runtime=os.environ.get('LOCALAPPDATA')
        if not runtime:self.skipTest('Original SEC Windows bulk archive private')
        zpath=Path(runtime)/'S153ResearchTerminal/runtime/bulk/sec/companyfacts.zip'
        if not zpath.is_file():self.skipTest('Private original SEC bulk absent')
        with zipfile.ZipFile(zpath) as z:
            for ticker,cik in [('CRMD','0001410098'),('ETON','0001710340'),('PENG','0001616533')]:
                receipt=depreciation_component(ticker,z.read(f'CIK{cik}.json'))
                self.assertEqual(receipt['status'],'VERIFIED_COMPONENT_RESEARCH_ONLY')
                self.assertIsNone(receipt['full_model_score'])
                self.assertEqual(receipt['inputs']['dep_current']['tag'],'Depreciation')
                self.assertEqual(receipt['inputs']['ppe_prior']['unit'],'USD')
                self.assertLess(abs(Decimal(receipt['depi_ratio_decimal'])-Decimal(receipt['independent_decimal_reference'])),Decimal('1e-50'))
            for ticker,cik in [('TMDX','0001756262'),('INOD','0000903651')]:
                receipt=depreciation_component(ticker,z.read(f'CIK{cik}.json'))
                self.assertEqual(receipt['status'],'DATA_MISSING')
                self.assertIn('dep_current',receipt['missing'])

    def test_source_tampering_fail_closed(self):
        runtime=os.environ.get('LOCALAPPDATA')
        if not runtime:self.skipTest('Private original SEC bulk absent')
        zpath=Path(runtime)/'S153ResearchTerminal/runtime/bulk/sec/companyfacts.zip'
        if not zpath.is_file():self.skipTest('Private original SEC bulk absent')
        with zipfile.ZipFile(zpath) as z: raw=z.read('CIK0001410098.json')
        with self.assertRaisesRegex(ValueError,'SEC_COMPANYFACTS_PIN_CHANGED'):
            depreciation_component('CRMD',raw+b' ')

if __name__=='__main__':unittest.main()
