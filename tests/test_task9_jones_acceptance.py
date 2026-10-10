"""Synthetic receipt tampering tests. Not issuer-score evidence."""
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from app.task9_jones_acceptance import verify_jones_task9_receipt


class _OfflineSec:
    def __init__(self,*args,**kwargs):
        self.requests=0


def receipt_template():
    return {'schema':'TASK9_JONES_FY2025_SEC_SIC7374_V4',
      'as_of':'2026-10-10T19:00:37+00:00',
      'ticker':'INOD','target_cik':'0000903651',
      'status':'VERIFIED_RESEARCH','canonical_accepted':False,
      'historical_pit_accepted':False,
      'verified_same_sic_independent_peers':20,'required_peers':20,
      'target':{'historical_sic':'7374','source_selected_count':8,
                'form_accession':'0001104659-26-020655',
                'header_sha256':'ab'*32,
                'accepted_at':'2026-02-26T22:22:13+00:00'},
      'target_financial_companyfacts_sha256':'6ccc9dcc93b9c303cee51c166f345350fb16258408c884e2ed5d1231f2741b38',
      'stop_reason':None,'s11_missing':[],
      's11_components':{'OLS_rank':3,'discretionary_accrual':.24692983352913417},
      's11_score':0.0,'s11_result_evidence_hash':'cd'*32,
      'independent_decimal_reference':{'within_1e_8':True}}


class Task9AcceptanceTests(unittest.TestCase):
    def setUp(self):
        temp=TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.cache=Path(temp.name)/'task9_jones'
        self.cache.mkdir()
        out=self.cache/'reports';out.mkdir()
        self.receipt=out/'task9_jones_fake.json'
        self.packet=receipt_template()
        self.save()

    def save(self):
        payload=json.dumps(self.packet).encode('utf8')
        self.receipt.write_bytes(payload)
        Path(str(self.receipt)+'.sha256').write_text(sha256(payload).hexdigest())

    @patch('app.task9_jones_acceptance.SECCache',_OfflineSec)
    @patch('app.task9_jones_acceptance.scan_task9')
    def test_real_zero_is_valid_on_independently_replayed_source(self,replay):
        replay.return_value=self.packet
        answer=verify_jones_task9_receipt(self.receipt,cache=self.cache)
        self.assertEqual(answer['score'],0.0)
        self.assertEqual(answer['eligible_peer_count'],20)
        self.assertEqual(answer['score_status'],'REAL_SCORE_ACCEPTED_RESEARCH')
        self.assertFalse(answer['historical_pit_accepted'])

    @patch('app.task9_jones_acceptance.SECCache',_OfflineSec)
    @patch('app.task9_jones_acceptance.scan_task9')
    def test_independent_replay_disagrees_with_resealed_score(self,replay):
        replay.return_value=self.packet.copy()
        self.packet['s11_score']=10.0
        self.packet['s11_components']['discretionary_accrual']=0.17
        self.save()
        with self.assertRaisesRegex(ValueError,'normalization|REPLAY'):
            verify_jones_task9_receipt(self.receipt,cache=self.cache)

    def test_receipt_hash_tamper_is_rejected_before_numeric_score(self):
        self.receipt.write_bytes(self.receipt.read_bytes()+b'x')
        with self.assertRaisesRegex(ValueError,'SHA_CHANGED'):
            verify_jones_task9_receipt(self.receipt,cache=self.cache)

    def test_19_peers_rejected_even_if_signed(self):
        self.packet['verified_same_sic_independent_peers']=19
        self.save()
        with self.assertRaisesRegex(ValueError,'not accepted'):
            verify_jones_task9_receipt(self.receipt,cache=self.cache)

    def test_historical_pit_falsely_accepted_rejected(self):
        self.packet['historical_pit_accepted']=True
        self.save()
        with self.assertRaisesRegex(ValueError,'not accepted'):
            verify_jones_task9_receipt(self.receipt,cache=self.cache)


if __name__=='__main__':unittest.main()
