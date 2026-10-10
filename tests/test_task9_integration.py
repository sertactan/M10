"""Proof the new financial receipt cannot promote S6/S14 or fake issuance."""
import json
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from app.scoring_completion import attach_task9_issuance_evidence
from app.task9_financial_recovery import recover_task9_evidence
from tests.test_task9_financial_recovery import _fixtures


def fresh_report():
    return {'stocks':[{'ticker':'INOD','quality':{'B_Q':{'score':None}},
                       'models':[{'model':'S6','score':None,'evidence':{}},
                                 {'model':'S14','score':None}],
                       'sec_quality_v3':{
                           'S6_partial_count':4,
                           'S6_partial':{'DELTA_REC':0.131164},
                           'missing_dechow':['RSST_WC_NCO_FIN','DOCUMENTED_ISSUANCE']
                       }}]}


class Task9IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.cache=self.root/'official-sec'
        self.cache.mkdir()
        facts,subs,bodies=_fixtures()
        self.facts=self.root/'companyfacts.json';self.facts.write_bytes(facts)
        self.sub=self.root/'submissions.json';self.sub.write_bytes(subs)
        for y,name in ((2024,'000141057825000194_inod-20241231x10k.htm'),
                       (2025,'000110465926020655_inod-20251231x10k.htm')):
            (self.cache/name).write_bytes(bodies[y])
        packet=recover_task9_evidence(facts,subs,bodies,
                                      retrieved_at='2026-10-10T18:33:11Z')
        private=self.root/'task9_private'
        private.mkdir()
        self.receipt=private/'financial_recovery.json'
        self.receipt.write_text(json.dumps(packet,ensure_ascii=False),encoding='utf8')
        Path(str(self.receipt)+'.sha256').write_text(sha256(self.receipt.read_bytes()).hexdigest())

    def test_five_real_features_replayed_no_score_promotion(self):
        report=fresh_report()
        attach_task9_issuance_evidence(report,self.receipt,self.facts,self.sub,self.cache)
        s=report['stocks'][0]
        self.assertEqual(s['sec_quality_v3']['S6_partial_count'],5)
        self.assertEqual(s['sec_quality_v3']['S6_partial']['ISSUE'],1)
        self.assertIsNone(s['task9_financial_evidence']['S6_score'])
        self.assertIsNone(s['task9_financial_evidence']['LVGI'])
        self.assertIsNone(s['models'][0]['score'])
        self.assertIsNone(s['models'][1]['score'])

    def test_hash_tampering_fails(self):
        self.receipt.write_bytes(self.receipt.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError,'SEAL_CHANGED'):
            attach_task9_issuance_evidence(fresh_report(),self.receipt,
                                           self.facts,self.sub,self.cache)

    def test_changed_official_filing_body_fails(self):
        source=self.cache/'000110465926020655_inod-20251231x10k.htm'
        source.write_bytes(source.read_bytes()+b'\n<!--changed-->')
        with self.assertRaisesRegex(ValueError,'REPLAY_MISMATCH'):
            attach_task9_issuance_evidence(fresh_report(),self.receipt,
                                           self.facts,self.sub,self.cache)

    def test_full_s6_cannot_be_overwritten(self):
        report=fresh_report()
        report['stocks'][0]['models'][0]['score']=80.0
        with self.assertRaisesRegex(ValueError,'cannot replace'):
            attach_task9_issuance_evidence(report,self.receipt,self.facts,self.sub,self.cache)

    def test_receipt_with_manufactured_s6_fails_even_if_resealed(self):
        p=json.loads(self.receipt.read_text());p['S6']=91.0
        self.receipt.write_text(json.dumps(p),encoding='utf8')
        Path(str(self.receipt)+'.sha256').write_text(sha256(self.receipt.read_bytes()).hexdigest())
        with self.assertRaisesRegex(ValueError,'promote'):
            attach_task9_issuance_evidence(fresh_report(),self.receipt,
                                           self.facts,self.sub,self.cache)


if __name__=='__main__':unittest.main()
