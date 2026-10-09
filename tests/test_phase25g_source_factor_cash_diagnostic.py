"""Unit tests for research-only Phase25g factor math, provenance, fail closed."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.phase25g_source_factor_cash_diagnostic import analyze, _safe_csv

NAMES=["DOYU","HUYA","IRS","SITC","TDG","ZIM"]

def fixture(root):
    p=root/"phase25f.json"
    events=[]
    by_ticker={}
    for i,name in enumerate(NAMES):
        sid=str(101+i)
        first="2024-08-01"
        later="2024-08-05"
        raw1=100
        adj1=50
        raw2=60
        adj2=45
        # All events are within one month, avoid claiming verified actions.
        events.append({
            "priority":"P1_MULTI_ALERT",
            "SimFinId":sid, "ticker":name,
            "source_event_kind":"SOURCE_FACTOR_WITHIN_MONTH_RANGE_5PCT",
            "source_months":"2024-08",
            "source_first_date":later if name=="HUYA" else first,
            "source_last_date":first if name=="HUYA" else later,
            "source_first_raw_close":raw2 if name=="HUYA" else raw1,
            "source_first_adj_close":adj2 if name=="HUYA" else adj1,
            "source_last_raw_close":raw1 if name=="HUYA" else raw2,
            "source_last_adj_close":adj1 if name=="HUYA" else adj2,
            "factor_range_pct_or_change_pct_or_adjusted_move_pct":33.333,
        })
        by_ticker[name]={
            "source_events":1, "first_source_date":first,
            "last_source_date":later,
        }
    data={
        "schema":"MERIDYEN_PHASE25F_P1_OFFICIAL_SOURCE_EVIDENCE_WORKLIST_V1",
        "status":"P1_INDEPENDENT_CORPORATE_ACTION_EVIDENCE_REVIEW_NEEDED_NOT_CERTIFIED",
        "window":{"start":"2024-01-01","end":"2025-09-30"},
        "P1_SimFinIds":6,
        "P1_dated_source_events":6,
        "P1_ticker_event_date_ranges":by_ticker,
        "review_rows":events,
        "separate_independent_evidence_obtained":False,
        "official_exchange_or_issuer_corporate_action_verified":0,
        "historical_issuer_CIK_verified":0,
        "adjusted_price_validated":0,
        "canonical_backtest_eligible_securities":0,
        "original_sources_modified":False,
        "operational_DB_modified":False,
        "models_modified":False,
        "network_requests":0,
        "paid_API_requests":0,
        "model_training_performed":False,
    }
    p.write_text(json.dumps(data),encoding="utf-8")
    return p


class TestPhase25g(unittest.TestCase):
    def test_template_with_six_incomplete_rows_fails_no_promotion(self):
        with TemporaryDirectory() as td:
            p=fixture(Path(td))
            with self.assertRaisesRegex(ValueError,"PHASE25F_UNSAFE_OR_UNEXPECTED_REPORT"):
                analyze(p)

    def test_source_month_factor_math(self):
        with TemporaryDirectory() as td:
            p=fixture(Path(td))
            data=json.loads(p.read_text())
            # Mimic genuine Phase25f 15-row input: two names get more
            # distinct, dated source observations to avoid duplicates.
            seq=[2,2,2,3,3,3]
            expanded=[]
            for name,n in zip(NAMES,seq):
                seed=next(r for r in data["review_rows"] if r["ticker"]==name)
                for k in range(n):
                    row=dict(seed)
                    day1=f"2024-08-{1+2*k:02d}"
                    day2=f"2024-08-{2+2*k:02d}"
                    row["source_first_date"]=day1
                    row["source_last_date"]=day2
                    row["source_months"]="2024-08"
                    row["source_first_raw_close"]=100
                    row["source_first_adj_close"]=50
                    row["source_last_raw_close"]=60
                    row["source_last_adj_close"]=45
                    expanded.append(row)
                data["P1_ticker_event_date_ranges"][name]={
                    "source_events":n,
                    "first_source_date":"2024-08-01",
                    "last_source_date":f"2024-08-{2*n:02d}",
                }
            data["review_rows"]=expanded
            data["P1_dated_source_events"]=15
            p.write_text(json.dumps(data))
            orig=p.read_bytes()
            report=analyze(p)
            self.assertEqual(report["p1_source_event_rows"],15)
            self.assertEqual(report["source_math"][0]["calendar_gap_days"],1)
            self.assertEqual(report["source_math"][0]["conditional_implied_single_cash_per_share"],33.333333)
            self.assertFalse(report["source_math"][0]["canonical_adjusted_price_approved"])
            self.assertEqual(report["canonical_backtest_eligible_securities"],0)
            self.assertEqual(p.read_bytes(),orig)

    def test_wrong_source_event_count_fails(self):
        with TemporaryDirectory() as td:
            p=fixture(Path(td))
            data=json.loads(p.read_text())
            data["P1_dated_source_events"]=15
            p.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,"PHASE25F_EVENT_COUNT_MISMATCH"):
                analyze(p)

    def test_csv_formula_escaped(self):
        self.assertEqual(_safe_csv("=SUM(1,2)"),"'=SUM(1,2)")
        self.assertEqual(_safe_csv("+1"),"'+1")
        self.assertEqual(_safe_csv("DOYU"),"DOYU")


if __name__=="__main__":
    unittest.main()
