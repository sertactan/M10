"""Real private SEC checks and negative acceptance cases for FY2025 INOD S9."""
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path

from app.scoring_v9_inod import calculate, write_or_verify


class InodResearchAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rt=Path(os.environ.get('LOCALAPPDATA',''))/'S153ResearchTerminal'/'runtime'
        zip_file=rt/'bulk/sec/companyfacts.zip'
        private=rt/'scoring_completion/v3_filing_bodies'
        paths=(rt/'sec_submissions/CIK0000903651.json',
          private/'000110465926020655_inod-20251231x10k.htm',
          private/'000141057825000194_inod-20241231x10k.htm')
        if not zip_file.is_file() or not all(x.is_file() for x in paths):
            cls.inputs=None
            return
        with zipfile.ZipFile(zip_file) as z:
            facts=z.read('CIK0000903651.json')
        cls.inputs=(facts,*(x.read_bytes() for x in paths))

    def _require(self):
        if self.inputs is None:self.skipTest('Private original SEC caches unavailable on GitHub CI')

    def test_real_official_inod_complete_s9_frozen(self):
        self._require()
        result=calculate(*self.inputs)
        self.assertEqual(result['positive_signal_count'],5)
        self.assertEqual(result['verified_signals'],9)
        self.assertEqual(result['score'],500/9)
        self.assertEqual(result['signals']['F_DELTA_LEVERAGE'],0)
        self.assertEqual(result['debt_reconciliation']['debt_FY2025_USD'],'0')
        self.assertEqual(result['debt_reconciliation']['debt_FY2024_USD'],'0')
        self.assertFalse(result['canonical_accepted'])

    def test_2024_official_body_tamper_fails_closed(self):
        self._require()
        inputs=list(self.inputs)
        inputs[3]=inputs[3]+b'\nSEC_TAMPER_MARKER'
        with self.assertRaisesRegex(ValueError,'FY2024_OFFICIAL_BODY_FINGERPRINT_CHANGED'):
            calculate(*inputs)

    def test_2025_cash_flow_tamper_fails_source(self):
        self._require()
        payload=json.loads(self.inputs[0]); payload['cik']=100
        inp=(json.dumps(payload).encode(),*self.inputs[1:])
        with self.assertRaisesRegex(ValueError,'COMPANYFACTS_CIK_MISMATCH'):
            calculate(*inp)

    def test_debt_evidence_cannot_be_discarded(self):
        self._require()
        inp=list(self.inputs)
        inp[2]=inp[2].replace(b'Wells Fargo',b'Wells Morgo',1)
        with self.assertRaisesRegex(ValueError,'OFFICIAL_FILING_BODY_SOURCE_IDENTITY_OR_SHA_CHANGED'):
            calculate(*inp)

    def test_private_receipt_replay_and_tamper(self):
        self._require()
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'report.json'
            write_or_verify(path,self.inputs)
            self.assertEqual(write_or_verify(path,self.inputs)['score'],500/9)
            path.write_text('{}',encoding='utf8')
            with self.assertRaisesRegex(ValueError,'V9_PRIVATE_S9_SOURCE_REPLAY_MISMATCH'):
                write_or_verify(path,self.inputs)


if __name__=='__main__':unittest.main()
