import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.phase25m_issuer_primary_action_evidence_triage import evaluate,REFERENCES

class TestPhase25m(unittest.TestCase):
    def mk(self,folder):
        path=Path(folder)/"25j.json"
        source=[]
        for ticker,num in [("CRCT",3),("IEP",6),("EC",4)]:
            for i in range(num):
                source.append({
                    "SimFinId":{"CRCT":"10384052","IEP":"980333","EC":"18766492"}[ticker],
                    "ticker":ticker,"source_event_type":"SOURCE_FACTOR_WITHIN_MONTH_RANGE_5PCT",
                    "source_observation_date_1":"2025-05-15",
                    "source_observation_date_2":"2025-05-23",
                    "present_day_CIK_candidate_NOT_verified":{
                      "CRCT":"0001828962","IEP":"0000813762","EC":"0001444406"}[ticker],
                })
        while len(source)<167:
            idx=len(source)
            source.append({
               "SimFinId":str(100000+idx),"ticker":f"X{idx}",
               "source_event_type":"SOURCE_FACTOR_WITHIN_MONTH_RANGE_5PCT",
               "source_observation_date_1":"2024-03-01",
               "source_observation_date_2":"2024-03-15",
               "present_day_CIK_candidate_NOT_verified":"0000000001"})
        path.write_text(json.dumps({
            "schema":"MERIDYEN_PHASE25J_P1_SEC_FILINGS_127_TRIAGE_V1",
            "other_research_candidates":127,"other_source_price_event_rows":167,
            "fully_verified_historical_SimFinId_CIK_pairs":0,
            "canonical_backtest_eligible_securities":0,
            "production_DB_modified":False,"WF9_allowed":False,
            "other_event_review_queue":source}))
        return path
    def test_thirteen_alerts_six_issuer_documents_no_canonical(self):
        with TemporaryDirectory() as td:
            p=self.mk(td)
            original=p.read_bytes()
            rep=evaluate(p)
            self.assertEqual(len(REFERENCES),6)
            self.assertEqual(rep["source_warnings_in_these_three_issuers"],13)
            self.assertEqual(rep["remaining_other_issuer_source_warnings_not_reviewed_in_this_phase"],154)
            self.assertEqual(rep["canonical_backtest_eligible"],0)
            self.assertEqual(rep["source_warning_events_fully_verified_ex_date_and_adjustment"],0)
            self.assertEqual(p.read_bytes(),original)
            self.assertFalse(rep["WF9_executed"])
    def test_canonical_prior_prohibited(self):
        with TemporaryDirectory() as td:
            p=self.mk(td)
            payload=json.loads(p.read_text())
            payload["canonical_backtest_eligible_securities"]=1
            p.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError,"P25J_PROVENANCE_INVALID"):
                evaluate(p)

if __name__=="__main__":
    unittest.main()
