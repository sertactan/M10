"""New completion regressions; synthetic fixtures are never real-stock score evidence."""
import copy
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from app.scoring_completion import completion_features, daily_features, model_execution, sec_acceptance_map, save_report, load_report, digest, SCHEMA
from app.recovered_quality import compute_quality, SOURCE_SHA256, INTERPOLATION_SHA256
from tests.test_phase28_real_scoring import fact, NOW

class CompletionTests(unittest.TestCase):
    def test_cagr_requires_exact_calendar_endpoint(self):
        rows=[fact('REVENUE',100,'2021-01-01','2021-12-31','ANNUAL'),
              fact('REVENUE',200,'2025-01-01','2025-12-31','ANNUAL')]
        self.assertNotIn('REVENUE_CAGR_3Y',completion_features(rows,NOW))
        rows.append(fact('REVENUE',100,'2022-01-01','2022-12-31','ANNUAL'))
        self.assertAlmostEqual(completion_features(rows,NOW)['REVENUE_CAGR_3Y']['value'],2**(1/3)-1)
    def test_exact_operating_leverage_and_margin_rules(self):
        rows=[]
        for year,rev,op,gp,cfo,cap in ((2024,100,10,40,15,5),(2025,120,20,60,30,6)):
            for metric,val in (('REVENUE',rev),('OPERATING_INCOME',op),('GROSS_PROFIT',gp),('OPERATING_CASH_FLOW',cfo),('CAPEX',cap)):
                rows.append(fact(metric,val,f'{year}-01-01',f'{year}-12-31','ANNUAL'))
        out=completion_features(rows,NOW)
        self.assertEqual(out['OL_Q']['value'],100)
        self.assertAlmostEqual(out['MI_Q']['value'],.4*(100*(20/120-10/100)/15*100)+.3*100+.3*(10/15*100))
        bad=[dict(r,period_start='2025-02-01') if r['metric']=='CAPEX' and r['period_end']=='2025-12-31' else r for r in rows]
        self.assertNotIn('MI_Q',completion_features(bad,NOW))
    def bars(self):
        return [dict(trade_date=(NOW.date()-timedelta(days=80-i)).isoformat(),o=10+i,h=12+i,l=9+i,c=11+i,volume=100+i,source='TEST',source_ref='fixture',retrieved_at=NOW.isoformat(),evidence_hash='ab'*32) for i in range(70)]
    def test_daily_future_duplicate_and_nonfinite_fail_closed(self):
        bars=self.bars()
        self.assertEqual(daily_features(bars,NOW)['status'],'RAW_RESEARCH_ONLY')
        for bad in ([*bars,bars[-1]],[*bars[:-1],dict(bars[-1],volume=float('nan'))],[dict(bars[0],retrieved_at=(NOW+timedelta(seconds=1)).isoformat())]):
            with self.assertRaises(ValueError):daily_features(bad,NOW)
    def test_real_engines_run_without_raw_accounting_in_score_map(self):
        data={'ticker':'TEST','security_id':'TEST','quote_price':10}
        features={'OL_Q':{'value':80},'RAW_NET_DEBT':{'value':-256692000}}
        aud,chain=model_execution(data,features,NOW)
        models=[m for m in aud if m['model'].startswith('S15')]
        self.assertEqual(len(models),3)
        for model in models:
            self.assertTrue(model['evidence']['engine_executed'])
            self.assertIsNone(model['score'])
            self.assertNotIn('RAW_NET_DEBT',model['evidence']['normalized_input_keys'])
    def test_report_hash_and_source_change_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);a=root/'a.db';b=root/'b.db';a.write_bytes(b'27');b.write_bytes(b'28')
            report={'schema':SCHEMA,'contract_sha256':SOURCE_SHA256,'interpolation_sha256':INTERPOLATION_SHA256,
                    'source_sha256':{'phase27':digest(a),'phase28':digest(b)},'canonical_securities':0,'canonical_dates':0,
                    'stocks':[]}
            out=root/'scoring_completion'/'report.json';save_report(report,out)
            a.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'SOURCE_HASH_CHANGED'):load_report(out,a,b)
            out.write_text('{}')
            with self.assertRaisesRegex(ValueError,'REPORT_HASH_CHANGED'):load_report(out,a,b)
    def test_quality_evidence_roundtrips_form_type(self):
        rows=[fact(m,v,'2025-01-01','2025-12-31','ANNUAL') for m,v in
              (('REVENUE',100),('NET_INCOME',10),('OPERATING_CASH_FLOW',12),('CAPEX',2))]
        q=compute_quality(rows,NOW)['S12']
        replay=compute_quality(q['evidence']['inputs'],NOW)['S12']
        self.assertEqual(q['score'],replay['score']);self.assertEqual(q['score'],84.75)
    def test_sec_acceptance_does_not_infer_available_at(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'sec.json'
            p.write_text(json.dumps({'cik':'0000903651','filings':{'recent':{'accessionNumber':['a'],'acceptanceDateTime':['2026-08-01T20:00:00Z']}}}))
            self.assertEqual(sec_acceptance_map(p,'903651'),{'a':'2026-08-01T20:00:00Z'})
            with self.assertRaisesRegex(ValueError,'issuer'):sec_acceptance_map(p,'2')

if __name__=='__main__':unittest.main()
