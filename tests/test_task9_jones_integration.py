"""Research S11=0 is complete, independently gated, and NOT full S14.

Mocked acceptance is synthetic. The true score comes from independently
replayed official SEC bytes in the separate Windows staging run.
"""
from datetime import datetime, timezone
from unittest.mock import patch
import unittest

from app.scoring_completion import attach_task9_jones_real_score
from app.recovered_quality import _result


def _fixture():
    now=datetime(2026,10,10,18,0,tzinfo=timezone.utc)
    q={k:_result(k,now,missing=['NOT_YET_VERIFIED']) for k in
       ('B_Q','S6','S7','S11','S12','S13')}
    for key,number in (('S7',100.0),('S12',91.528866)):
        q[key]=_result(key,now,score=number,missing=[])
    models=[{'model':key,'score':q[key]['score'],'status':q[key]['status'],
             'missing':q[key]['missing'],'evidence':q[key]['evidence']}
            for key in q]
    models.append({'model':'S14','score':None,'status':'DATA_MISSING',
                   'missing':['B_Q','S6','S11','S13'],
                   'present':2,'evidence':{'legs':q}})
    models.extend({'model':f'MODEL_{i}','score':None,'missing':[],
                   'evidence':{}} for i in range(13))
    stock={'ticker':'INOD','quality':q,'models':models,'as_of':now.isoformat(),
           'full_model_count':2}
    others=[{'ticker':t,'full_model_count':n,'models':[], 'quality':{}}
            for t,n in (('TMDX',2),('CRMD',2),('PENG',2),('ETON',1))]
    return {'stocks':[stock,*others],'full_model_count':9,
            'full_score_securities':5,'canonical_securities':0,'canonical_dates':0}


def _verified(score=0.0):
    return {'score':score,'score_status':'REAL_SCORE_ACCEPTED_RESEARCH',
            'model':'S11','model_version':'S11_MODIFIED_JONES_SOURCE_RECOVERED_V1_RESEARCH',
            'period_end':'2025-12-31','components':{'discretionary_accrual':.24692983352913417,
            'OLS_rank':3},'source_file_sha256':'ab'*32,
            'eligible_peer_count':20,'source_cik':'0000903651',
            'as_of':'2026-10-10T19:00:37+00:00','historical_pit_accepted':False,
            'canonical_accepted':False,'independent_confirmed':True}


class Task9JonesIntegrationTests(unittest.TestCase):
    @patch('app.task9_jones_acceptance.verify_jones_task9_receipt')
    def test_valid_zero_score_is_complete_but_s14_not_complete(self,verifier):
        verifier.return_value=_verified()
        report=_fixture()
        attach_task9_jones_real_score(report,'private-receipt','private-cache')
        stock=report['stocks'][0]
        model=next(x for x in stock['models'] if x['model']=='S11')
        self.assertEqual(model['score'],0.0)
        self.assertEqual(stock['quality']['S11']['score'],0.0)
        self.assertEqual(model['status'],'REAL_SCORE_ACCEPTED_RESEARCH')
        self.assertEqual(stock['full_model_count'],3)
        self.assertEqual(report['full_model_count'],10)
        frozen=next(x for x in stock['models'] if x['model']=='S14')
        self.assertEqual(frozen['present'],3)
        self.assertEqual(frozen['missing'],['B_Q','S6','S13'])
        self.assertIsNone(frozen['score'])

    @patch('app.task9_jones_acceptance.verify_jones_task9_receipt')
    def test_numerical_nonzero_synthetic_still_follows_true_leg_contract(self,verifier):
        verifier.return_value=_verified(score=20.0)
        report=_fixture()
        attach_task9_jones_real_score(report,'receipt','cache')
        stock=report['stocks'][0]
        self.assertEqual(stock['quality']['S11']['score'],20.0)
        self.assertIsNone(next(x for x in stock['models'] if x['model']=='S14')['score'])

    @patch('app.task9_jones_acceptance.verify_jones_task9_receipt')
    def test_never_replace_already_scored_s11(self,verifier):
        verifier.return_value=_verified()
        report=_fixture()
        next(x for x in report['stocks'][0]['models'] if x['model']=='S11')['score']=90
        with self.assertRaisesRegex(ValueError,'overwritten'):
            attach_task9_jones_real_score(report,'receipt','cache')

    @patch('app.task9_jones_acceptance.verify_jones_task9_receipt')
    def test_never_merge_research_with_canonical(self,verifier):
        verifier.return_value=_verified()
        report=_fixture()
        report['canonical_securities']=1
        with self.assertRaisesRegex(ValueError,'Research staging'):
            attach_task9_jones_real_score(report,'receipt','cache')


if __name__=='__main__':
    unittest.main()
