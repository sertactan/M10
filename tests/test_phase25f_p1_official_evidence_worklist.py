import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.phase25f_p1_official_evidence_worklist import build, _safe_csv


def sample(root:Path):
    p=root/"phase25e.json"
    a={"SimFinId":"101","ticker":"HUYA","priority":"P1_MULTI_ALERT",
       "intra_month_ranges":1,"factor_month_boundaries":1,
       "extreme_adjusted_month_boundaries":0,"dated_source_event_count":2}
    b={"SimFinId":"102","ticker":"ZIM","priority":"P2_FACTOR_CHANGE",
       "intra_month_ranges":0,"factor_month_boundaries":1,
       "extreme_adjusted_month_boundaries":0,"dated_source_event_count":1}
    def ob(date, raw,adj):
        return {"source_date":date,"raw_close":raw,"source_adj_close":adj,
                "source_close_to_adjusted_factor":raw/adj}
    events=[
        {"SimFinId":"101","ticker":"HUYA","priority":"P1_MULTI_ALERT",
         "present_day_CIK_candidate_NOT_verified":"0000011111",
         "kind":"SOURCE_FACTOR_WITHIN_MONTH_RANGE_5PCT",
         "month":"2024-02","factor_range_pct":100.0,
         "observations":[ob("2024-02-01",10,10),ob("2024-02-20",10,5)],
         "split_or_dividend_proven":False,"historical_CIK_certified":False},
        {"SimFinId":"101","ticker":"HUYA","priority":"P1_MULTI_ALERT",
         "present_day_CIK_candidate_NOT_verified":"0000011111",
         "kind":"SOURCE_FACTOR_MONTH_BOUNDARY_5PCT",
         "months":["2024-02","2024-03"],
         "absolute_factor_ratio_change_pct":100.0,
         "observations":[ob("2024-02-29",10,5),ob("2024-03-01",10,10)],
         "split_or_dividend_proven":False,"historical_CIK_certified":False},
        {"SimFinId":"102","ticker":"ZIM","priority":"P2_FACTOR_CHANGE",
         "present_day_CIK_candidate_NOT_verified":"0000022222",
         "kind":"SOURCE_FACTOR_MONTH_BOUNDARY_5PCT",
         "months":["2024-03","2024-04"],
         "absolute_factor_ratio_change_pct":100.0,
         "observations":[ob("2024-03-29",10,5),ob("2024-04-01",10,10)],
         "split_or_dividend_proven":False,"historical_CIK_certified":False},
    ]
    data={
        "schema":"MERIDYEN_PHASE25E_DATED_SIMFIN_PRICE_ANOMALY_SOURCE_EVIDENCE_V1",
        "status":"DATED_SOURCE_PRICE_ANOMALIES_RESEARCH_ONLY_NOT_CANONICAL",
        "window":{"start":"2024-01-01","end":"2025-09-30"},
        "source_SHA256":"1"*64,
        "candidate_SimFinIds":2,
        "priority_counts":{"P1_MULTI_ALERT":1,"P2_FACTOR_CHANGE":1},
        "P1_candidates":[a],
        "per_candidate":[a,b],
        "source_only_event_observations":events,
        "event_counts":{"SOURCE_FACTOR_WITHIN_MONTH_RANGE_5PCT":1,
                        "SOURCE_FACTOR_MONTH_BOUNDARY_5PCT":2},
        "canonical_backtest_eligible_securities":0,
        "historical_identity_certifications":0,
        "adjusted_prices_certified":0,
        "split_verified":0,"dividend_verified":0,
        "database_modified":False,"source_price_modified":False,
        "SEC_records_modified":False,"models_modified":False,
        "model_training_performed":False,"network_requests":0,"paid_API_requests":0,
    }
    p.write_text(json.dumps(data),encoding="utf-8")
    return p


class TestPhase25fP1OfficialEvidenceWorklist(unittest.TestCase):
    def test_p1_only_source_dates_evidence_remains_unverified(self):
        with TemporaryDirectory() as d:
            path=sample(Path(d))
            before=path.read_bytes()
            r=build(path)
            self.assertEqual(r["P1_SimFinIds"],1)
            self.assertEqual(r["P1_dated_source_events"],2)
            self.assertEqual(r["P1_ticker_event_date_ranges"]["HUYA"]["first_source_date"],"2024-02-01")
            self.assertEqual(r["P1_ticker_event_date_ranges"]["HUYA"]["last_source_date"],"2024-03-01")
            self.assertEqual(r["review_rows"][0]["official_evidence_url_TO_RESEARCH"],"")
            self.assertEqual(r["official_exchange_or_issuer_corporate_action_verified"],0)
            self.assertEqual(r["historical_issuer_CIK_verified"],0)
            self.assertEqual(r["canonical_backtest_eligible_securities"],0)
            self.assertEqual(before,path.read_bytes())

    def test_refuse_fake_source_split_confirmation(self):
        with TemporaryDirectory() as d:
            path=sample(Path(d))
            data=json.loads(path.read_text())
            data["source_only_event_observations"][0]["split_or_dividend_proven"]=True
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,"EVENT_KIND_OR_CERTIFICATION_UNSAFE"):
                build(path)

    def test_source_factor_mismatch_rejected(self):
        with TemporaryDirectory() as d:
            path=sample(Path(d))
            data=json.loads(path.read_text())
            data["source_only_event_observations"][0]["observations"][1]["source_close_to_adjusted_factor"]=1
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,"SOURCE_FACTOR_MISMATCH"):
                build(path)

    def test_wrong_event_count_detected(self):
        with TemporaryDirectory() as d:
            path=sample(Path(d))
            data=json.loads(path.read_text())
            data["per_candidate"][0]["factor_month_boundaries"]=2
            data["P1_candidates"][0]["factor_month_boundaries"]=2
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,"PHASE25E_PER_CANDIDATE_EVENTS_NOT_RECONCILED"):
                build(path)

    def test_input_canonical_certification_rejected(self):
        with TemporaryDirectory() as d:
            path=sample(Path(d))
            data=json.loads(path.read_text())
            data["canonical_backtest_eligible_securities"]=1
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,"PHASE25E_NOT_SAFE"):
                build(path)

    def test_excel_formula_safe(self):
        self.assertEqual(_safe_csv("=CMD(A1)"),"'=CMD(A1)")
        self.assertEqual(_safe_csv("+EXPLOIT"),"'+EXPLOIT")
        self.assertEqual(_safe_csv("HUYA"),"HUYA")


if __name__=="__main__":
    unittest.main()
