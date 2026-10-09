import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from scripts.phase25k_canonical_acceptance_ledger import reconcile

def fixture(root):
    i=root/"phase25i.json";j=root/"phase25j.json"
    i.write_text(json.dumps({"schema":"MERIDYEN_PHASE25I_REAL_MARKET_PIT_TRAINING_GATE_V1",
        "status":"FULL_CHAIN_REAL_DATA_BLOCKED_NOT_TRAINED","pit_backtest_eligible":False,
        "walk_forward_executed":False,"Learning_V3_executed":False,"source_db_modified":False,
        "counts":{"membership":[0,0,0],"canonical_backtest_price":[0,0],
                  "corporate_actions":[0],"complete_WF5":[0],"complete_WF6":[0]},
        "blockers":["NO_AUTHORITATIVE_ADJUSTED_BACKTEST_PRICE_SELECTION"]}))
    p1=[{"SimFinId":str(n),"ticker":t,"present_day_CIK_candidate":str(n),
         "SEC_filing_url":"https://www.sec.gov/Archives/edgar/data/"+str(n),
         "historical_SimFinId_to_CIK_certified":False}
        for n,t in enumerate(["DOYU","HUYA","IRS","SITC","TDG","ZIM"],1)]
    other=[]
    for n in range(7,134):
        q="P2_FACTOR_CHANGE" if n<95 else "P3_EXTREME_ADJ_RETURN_ONLY"
        for k in range(2 if n<47 else 1):
            other.append({"SimFinId":str(n),"ticker":f"X{n}",
              "priority":q,"present_day_CIK_candidate_NOT_verified":str(n),
              "canonical_adjusted_prices_verified":False,
              "historic_security_identity_verified":False,
              "delisting_corporate_action_verified":False})
    while len(other)<167:
        other.append(dict(other[-1]))
    j.write_text(json.dumps({"schema":"MERIDYEN_PHASE25J_P1_SEC_FILINGS_127_TRIAGE_V1",
        "p1_count":6,"other_research_candidates":127,
        "other_source_price_event_rows":167,
        "fully_verified_historical_SimFinId_CIK_pairs":0,
        "canonical_backtest_eligible_securities":0,
        "production_DB_modified":False,"WF9_allowed":False,
        "Learning_V3_allowed":False,"p1_document_refs":p1,
        "other_event_review_queue":other}))
    return i,j

class TestCanonicalLedger(unittest.TestCase):
    def test_133_cannot_be_promoted(self):
        with TemporaryDirectory() as d:
            i,j=fixture(Path(d))
            rep=reconcile(i,j)
            self.assertEqual(rep["research_candidate_ids"],133)
            self.assertEqual(rep["accepted_canonical_securities"],0)
            self.assertFalse(rep["actual_WF9_executed"])
            self.assertFalse(rep["actual_Learning_V3_executed"])
    def test_promoted_p25i_rejected(self):
        with TemporaryDirectory() as d:
            i,j=fixture(Path(d))
            data=json.loads(i.read_text())
            data["pit_backtest_eligible"]=True
            i.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,"REAL_RESEARCH_INPUTS_NOT_FAIL_CLOSED"):
                reconcile(i,j)
if __name__=="__main__":
    unittest.main()
