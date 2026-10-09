import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from scripts.phase25g_source_factor_cash_diagnostic import COLS
from scripts.phase25h_official_cash_source_reconciliation import REFERENCES, evaluate

def fixture(path):
    rows=[]
    for name,day1,day2 in REFERENCES:
        p0,a0,p1,a1=100.0,80.0,90.0,85.0
        factor0=p0/a0; factor1=p1/a1
        source={
            "SimFinId":str(["DOYU","HUYA","IRS","SITC","TDG","ZIM"].index(name)+1),
            "ticker":name, "source_event_kind":"SOURCE_FACTOR_WITHIN_MONTH_RANGE_5PCT",
            "source_event_months":day1[:7],"source_before_date":day1,
            "source_after_date":day2,"calendar_gap_days":4,
            "source_before_raw_close":p0,"source_after_raw_close":p1,
            "source_before_adj_close":a0,"source_after_adj_close":a1,
            "source_before_factor":round(factor0,9),
            "source_after_factor":round(factor1,9),
            "source_factor_pct_change_signed":-15.3,
            "conditional_implied_single_cash_per_share":round(p0*(1-factor1/factor0),6),
            "source_raw_close_return_pct":-10,
            "source_adjusted_close_return_pct":6.25,
            "source_original_anomaly_pct":6.5,
            "research_classification":"SOURCE_RATIO_DIAGNOSTIC_NO_OFFICIAL_MATCH",
            "official_corporate_action_evidence_independently_confirmed":False,
            "canonical_adjusted_price_approved":False,
        }
        assert set(source)==set(COLS)
        rows.append(source)
    data={
        "schema":"MERIDYEN_PHASE25G_SOURCE_FACTOR_CASH_IMPLICATION_DIAG_V1",
        "status":"SOURCE_FACTOR_CASH_IMPLICATIONS_RESEARCH_ONLY_NOT_OFFICIAL_VERIFICATION",
        "p1_source_event_rows":15,
        "p1_tickers":["DOYU","HUYA","IRS","SITC","TDG","ZIM"],
        "independent_corporate_actions_matched":0,
        "canonical_backtest_eligible_securities":0,
        "vendor_adjustment_methodology_verified":False,
        "production_DB_modified":False,
        "SEC_records_modified":False,
        "models_modified":False,
        "network_requests":0,
        "paid_API_requests":0,
        "training_performed":False,
        "source_math":rows,
    }
    path.write_text(json.dumps(data))
    return data

class TestPhase25h(unittest.TestCase):
    def test_all_15_joined_to_references_but_not_certified(self):
        with TemporaryDirectory() as d:
            p=Path(d)/"source.json"
            fixture(p)
            orig=p.read_bytes()
            a=evaluate(p)
            self.assertEqual(a["source_warning_rows"],15)
            self.assertEqual(a["reference_count_unique_primary_cash_events"],13)
            self.assertEqual(a["canonical_backtest_eligible_securities"],0)
            self.assertFalse(a["walk_forward_backtest_allowed"])
            self.assertFalse(a["Learning_V3_allowed"])
            self.assertEqual(orig,p.read_bytes())
            lookup={(r["ticker"],r["source_before_date"]):r for r in a["review_rows"]}
            self.assertEqual(lookup["DOYU","2024-08-12"]["manual_review_class"],"REFERENCE_DATE_OUTSIDE_PRICE_OBSERVATIONS")
            self.assertEqual(lookup["SITC","2025-08-13"]["manual_review_class"],"REFERENCE_DATE_OUTSIDE_PRICE_OBSERVATIONS")
            self.assertEqual(lookup["IRS","2024-11-19"]["official_date_type"],"RECORD_DATE")
    def test_refuse_mutated_g_source_price(self):
        with TemporaryDirectory() as d:
            p=Path(d)/"source.json"
            data=fixture(p)
            data["source_math"][0]["conditional_implied_single_cash_per_share"]=999
            p.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,"PROVENANCE_MISMATCH"):
                evaluate(p)
    def test_refuse_stale_identity_certification(self):
        with TemporaryDirectory() as d:
            p=Path(d)/"source.json"
            data=fixture(p)
            data["canonical_backtest_eligible_securities"]=1
            p.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,"PHASE25G_RESEARCH_PROVENANCE_FAILURE"):
                evaluate(p)
    def test_refuse_missing_event(self):
        with TemporaryDirectory() as d:
            p=Path(d)/"source.json"
            data=fixture(p)
            data["source_math"].pop()
            p.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,"PHASE25G_EVENT_COUNT_CHANGE"):
                evaluate(p)

if __name__=="__main__":
    unittest.main()
