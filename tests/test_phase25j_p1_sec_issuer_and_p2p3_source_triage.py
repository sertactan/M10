import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.phase25j_p1_sec_issuer_and_p2p3_source_triage import build,OFFICIAL_DOCS

def fixtures(root):
    names=sorted(OFFICIAL_DOCS)
    entries=[]
    for j in range(133):
        name=names[j] if j<6 else f"Q{j:04d}"
        priority="P1_MULTI_ALERT" if j<6 else ("P2_FACTOR_CHANGE" if j<94 else "P3_EXTREME_ADJ_RETURN_ONLY")
        cik=OFFICIAL_DOCS[name]["CIK"] if j<6 else f"{2000000+j:010d}"
        entries.append({"SimFinId":str(j+1000),"ticker":name,
                        "priority":priority,"present_day_CIK_candidate_NOT_verified":cik,
                        "research_only_NOT_PIT":True})
    refs=[{"SimFinId":x["SimFinId"],"ticker_strings":[x["ticker"]],
           "candidate_CIKs_NOT_verified":[x["present_day_CIK_candidate_NOT_verified"]]} for x in entries]
    evs=[]
    per=[]
    for j,x in enumerate(entries):
        count=3 if j<3 else 2 if j<6 else 2 if 6<=j<45 or j==94 else 1
        # 6 P1: 3*3+3*2=15; P2: 39*2+49*1=127; P3: 1*2+38*1=40.
        per.append({"SimFinId":x["SimFinId"],"dated_source_event_count":count})
        for k in range(count):
            evs.append({"SimFinId":x["SimFinId"],"ticker":x["ticker"],
                        "priority":x["priority"],
                        "kind":"SOURCE_FACTOR_WITHIN_MONTH_RANGE_5PCT",
                        "split_or_dividend_proven":False,"historical_CIK_certified":False,
                        "observations":[{"source_date":"2024-04-01","raw_close":10,
                                         "source_adj_close":9},
                                        {"source_date":"2024-04-05","raw_close":9,
                                         "source_adj_close":8}]})
    assert len(evs)==182,(len(evs),sum(x["dated_source_event_count"] for x in per))
    a=root/"phase24.json";d=root/"phase25d.json";e=root/"phase25e.json"
    a.write_text(json.dumps({
        "status":"SIMFIN_ID_TO_CIK_CANDIDATES_ONLY_ZERO_HISTORICAL_ID_CERTIFICATIONS",
        "historical_identity_certifications":0,"canonical_price_selections_written":0,
        "model_training_performed":False,"candidate_records":refs}))
    d.write_text(json.dumps({
        "status":"UNIQUE_SOURCE_FACTOR_AND_RETURN_ALERT_WORKLIST_RESEARCH_ONLY_NOT_CANONICAL",
        "unique_review_candidates":133,"canonical_backtest_eligible_securities":0,
        "database_modified":False,"review_queue":entries}))
    e.write_text(json.dumps({
        "status":"DATED_SOURCE_PRICE_ANOMALIES_RESEARCH_ONLY_NOT_CANONICAL",
        "candidate_SimFinIds":133,"canonical_backtest_eligible_securities":0,
        "database_modified":False,"models_modified":False,"network_requests":0,
        "paid_API_requests":0,"model_training_performed":False,
        "source_only_event_observations":evs,"per_candidate":per}))
    return a,d,e

class TestPhase25j(unittest.TestCase):
    def test_real_shape_6_plus_127_and_182(self):
        with TemporaryDirectory() as td:
            root=Path(td)
            a,d,e=fixtures(root)
            originals=[x.read_bytes() for x in (a,d,e)]
            rep=build(a,d,e)
            self.assertEqual(rep["p1_count"],6)
            self.assertEqual(rep["other_research_candidates"],127)
            self.assertEqual(rep["other_source_price_event_rows"],167)
            self.assertEqual(rep["events_by_priority"],{
                "P1_MULTI_ALERT":15,"P2_FACTOR_CHANGE":127,
                "P3_EXTREME_ADJ_RETURN_ONLY":40})
            self.assertEqual(rep["fully_verified_historical_SimFinId_CIK_pairs"],0)
            self.assertFalse(rep["WF9_allowed"])
            self.assertFalse(rep["Learning_V3_allowed"])
            self.assertEqual([x.read_bytes() for x in (a,d,e)],originals)
    def test_forged_p1_current_cik_fails(self):
        with TemporaryDirectory() as td:
            a,d,e=fixtures(Path(td))
            doc=json.loads(d.read_text())
            doc["review_queue"][0]["present_day_CIK_candidate_NOT_verified"]="0000000001"
            d.write_text(json.dumps(doc))
            with self.assertRaisesRegex(ValueError,"SIMFINID_CURRENT_CIK_IDENTITY_MISMATCH"):
                build(a,d,e)
    def test_fake_corporate_action_confirmation_rejected(self):
        with TemporaryDirectory() as td:
            a,d,e=fixtures(Path(td))
            doc=json.loads(e.read_text())
            doc["source_only_event_observations"][20]["split_or_dividend_proven"]=True
            e.write_text(json.dumps(doc))
            with self.assertRaisesRegex(ValueError,"INCORRECT_CANONICAL_PROMOTION"):
                build(a,d,e)

if __name__=="__main__":
    unittest.main()
