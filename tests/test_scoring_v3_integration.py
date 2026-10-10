"""Synthetic end-to-end private SEC V3 receipts never elevate scores."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from app.scoring_completion import attach_v3_financial_quality
from app.scoring_v3_sec_quality import recover,save_private
from tests.test_scoring_v3_sec_quality import fixture


def report():
    first={'ticker':'INOD', 'quality':{'B_Q':{'score':None}},
           'models':[{'model':'S6','score':None},{'model':'S14','score':None}]}
    return {'stocks':[first,*[{'ticker':t} for t in ('TMDX','CRMD','PENG','ETON')]]}


class SecV3ReceiptTests(unittest.TestCase):
    def test_source_sealed_local_attach_without_full_model_promotion(self):
        raw,subs=fixture()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'scoring_completion';root.mkdir()
            src=root/'companyfacts.json';src.write_bytes(raw)
            filings=root/'submissions.json';filings.write_bytes(subs)
            receipt=root/'quality_v3.json'
            original=recover(raw,subs,retrieved_at='2026-10-11T00:00:00Z')
            save_private(original,receipt)
            r=report()
            attach_v3_financial_quality(r,receipt,src,filings)
            v3=r['stocks'][0]['sec_quality_v3']
            self.assertEqual(v3['B_Q_risk_count'],4)
            self.assertEqual(v3['S6_partial_count'],4)
            self.assertIsNone(v3['B_Q_score'])
            self.assertIsNone(v3['S6_score'])
            self.assertIsNone(v3['S14_score'])
            self.assertFalse(v3['historical_pit_accepted'])
            altered=copy.deepcopy(r)
            altered['stocks'][0]['models'][0]['score']=50
            with self.assertRaisesRegex(ValueError,'overwrite'):
                attach_v3_financial_quality(altered,receipt,src,filings)
            src.write_bytes(raw+b' ')
            with self.assertRaisesRegex(ValueError,'SOURCE_CHANGED'):
                attach_v3_financial_quality(report(),receipt,src,filings)

    def test_tampered_research_receipt_rejected_before_attachment(self):
        raw,subs=fixture()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'scoring_completion';root.mkdir()
            src=root/'companyfacts.json';src.write_bytes(raw)
            filing=root/'submissions.json';filing.write_bytes(subs)
            receipt=root/'quality_v3.json'
            save_private(recover(raw,subs,retrieved_at='2026-10-11T00:00:00Z'),receipt)
            data=json.loads(receipt.read_text())
            data['beneish']['verified_risk_count']=7
            receipt.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,'SEAL_CHANGED'):
                attach_v3_financial_quality(report(),receipt,src,filing)


if __name__=='__main__':
    unittest.main()
