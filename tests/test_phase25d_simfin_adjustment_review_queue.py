import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.phase25d_simfin_adjustment_review_queue import (
    analyze, _safe_cell
)


def fixture(folder:Path):
    b=folder/"phase25b.json"
    c=folder/"phase25c.json"
    sha="ab"*32
    records=[]
    flags=[(2,1,0),(0,1,2),(0,0,1),(0,0,0),(1,0,0)]
    for n in range(5):
        ticker=f"TK{n}"
        records.append({
            "SimFinId":str(100+n),
            "ticker":ticker,
            "candidate_CIK_NOT_verified":f"{n+1:010d}",
            "valid_ohlc_positive_source_adjusted_rows":421,
            "daily_PIT_or_adjustment_certified":False,
        })
    b.write_text(json.dumps({
        "schema":"MERIDYEN_PHASE25B_SIMFIN_DISTINCT_DATE_QUALITY_RESEARCH_V1",
        "status":"DISTINCT_SIMFINID_DATE_COUNTS_VERIFIED_RESEARCH_ONLY_NOT_PIT",
        "window":{"start":"2024-01-01","end":"2025-09-30"},
        "canonical_eligible":0,
        "historical_SimFinId_CIK_certifications":0,
        "price_adjustment_certifications":0,
        "operational_DB_modified":False,
        "source_file_modified":False,
        "model_training_performed":False,
        "source_price_file_SHA256":sha,
        "phase25a_prior_candidate_21months":5,
        "candidate_depth_records":records,
    }))
    c_records=[]
    for idx,(intra,boundary,extreme) in enumerate(flags):
        c_records.append({
            "SimFinId":str(100+idx),
            "ticker":f"TK{idx}",
            "candidate_CIK_NOT_historical_verified":f"{idx+1:010d}",
            "qualified_source_rows":421,
            "months_covered":21,
            "source_close_to_adjusted_factor_range_over_5pct_months":intra,
            "factor_change_over_5pct_month_boundaries":boundary,
            "extreme_source_adjusted_month_boundary_returns":extreme,
            "corporate_actions_independently_verified":0,
            "adjustment_and_delisting_certified":False,
        })
    c.write_text(json.dumps({
        "schema":"MERIDYEN_PHASE25C_SIMFIN_ADJUSTMENT_FACTOR_CANDIDATES_V1",
        "status":"SIMFIN_ADJUSTED_PRICE_FACTOR_SOURCE_TRIAGE_NOT_SPLIT_DIVIDEND_PROOF",
        "window":{"start":"2024-01-01","end":"2025-09-30"},
        "source_sha256":sha,
        "SimFinIds_reviewed":5,
        "metrics":{
            "candidate_ids_with_factor_5pct_intra_month":2,
            "candidate_ids_with_factor_5pct_month_boundary":2,
            "candidate_ids_with_extreme_adj_month_boundary_return":2,
            "intra_month_factor_5pct_months":3,
            "factor_5pct_boundary_events":2,
            "extreme_adjusted_month_boundary_moves":3,
        },
        "candidate_factor_aggregate_records":c_records,
        "certified_adjusted_prices":0,
        "canonical_backtest_eligible_securities":0,
        "independent_split_events_verified":0,
        "independent_dividend_events_verified":0,
        "database_modified":False,
        "source_price_modified":False,
        "models_modified":False,
        "training_performed":False,
        "network_requests":0,
        "paid_API_requests":0,
    }))
    return b,c


class TestPhase25dReviewQueue(unittest.TestCase):
    def test_unique_union_and_priorities_not_canonical(self):
        with TemporaryDirectory() as td:
            b,c=fixture(Path(td))
            orig1=b.read_bytes()
            orig2=c.read_bytes()
            report,queue=analyze(b,c)
            self.assertEqual(report["SimFinIds_reviewed"],5)
            self.assertEqual(report["unique_review_candidates"],4)
            self.assertEqual(report["metrics"]["unique_ids_with_multiple_alert_classes"],2)
            self.assertEqual(report["metrics"]["extreme_adjusted_move_only_ids"],1)
            self.assertEqual(report["metrics"]["unique_ids_with_source_factor_alert"],3)
            self.assertEqual(report["metrics"]["priority_P1_MULTI_ALERT"],2)
            self.assertEqual(report["metrics"]["priority_P2_FACTOR_CHANGE"],1)
            self.assertEqual(report["metrics"]["priority_P3_EXTREME_ADJ_RETURN_ONLY"],1)
            self.assertEqual(len(queue),4)
            self.assertEqual(queue[0]["priority"],"P1_MULTI_ALERT")
            self.assertEqual(queue[-1]["priority"],"P3_EXTREME_ADJ_RETURN_ONLY")
            self.assertEqual(report["canonical_backtest_eligible_securities"],0)
            self.assertEqual(report["split_events_independently_verified"],0)
            self.assertEqual(b.read_bytes(),orig1)
            self.assertEqual(c.read_bytes(),orig2)

    def test_refuse_fake_corporate_action_verification(self):
        with TemporaryDirectory() as td:
            b,c=fixture(Path(td))
            data=json.loads(c.read_text())
            data["independent_split_events_verified"]=1
            c.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,"PHASE25C_NOT_SAFE"):
                analyze(b,c)

    def test_refuse_tampered_flag_aggregate(self):
        with TemporaryDirectory() as td:
            b,c=fixture(Path(td))
            data=json.loads(c.read_text())
            data["metrics"]["candidate_ids_with_factor_5pct_intra_month"]=999
            c.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,"PHASE25C_AGGREGATE_METRICS_INCONSISTENT"):
                analyze(b,c)

    def test_refuse_cik_mismatch(self):
        with TemporaryDirectory() as td:
            b,c=fixture(Path(td))
            data=json.loads(c.read_text())
            data["candidate_factor_aggregate_records"][0]["candidate_CIK_NOT_historical_verified"]="0000000999"
            c.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,"PHASE25B_25C_CANDIDATE_PROVENANCE_MISMATCH"):
                analyze(b,c)

    def test_refuse_nonpositive_provenance_change(self):
        with TemporaryDirectory() as td:
            b,c=fixture(Path(td))
            data=json.loads(b.read_text())
            data["source_price_file_SHA256"]="bb"*32
            b.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,"PHASE25B_25C_SHA256_PROVENANCE_MISMATCH"):
                analyze(b,c)

    def test_csv_formula_injection_escaped(self):
        self.assertEqual(_safe_cell("=1+2"),"'=1+2")
        self.assertEqual(_safe_cell("@SUM(A1)"),"'@SUM(A1)")
        self.assertEqual(_safe_cell("TK42"),"TK42")


if __name__=="__main__":
    unittest.main()
