import hashlib
import json
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts.phase25c_simfin_adjustment_factor_triage import analyze
from scripts.phase25b_simfin_distinct_daily_depth_audit import PER_MONTH_KEYS


def sample(root):
    csv_path=root/"source.csv"
    rows=["Ticker,SimFinId,Date,Open,High,Low,Close,Adj. Close"]
    for month in PER_MONTH_KEYS:
        yy,mm=map(int,month.split("-"))
        ds=f"{yy}-{mm:02d}-15"
        # One source factor discontinuity in January 2025, which must be
        # classified ONLY as a candidate, never verified corporate action.
        adjusted="5" if month=="2025-01" else "10"
        rows.append(f"TEST,101,{ds},10,12,9,10,{adjusted}")
    csv_path.write_text("\n".join(rows)+"\n",encoding="utf-8")
    sha=hashlib.sha256(csv_path.read_bytes()).hexdigest()
    report_path=root/"phase25b.json"
    report_path.write_text(json.dumps({
        "schema":"MERIDYEN_PHASE25B_SIMFIN_DISTINCT_DATE_QUALITY_RESEARCH_V1",
        "status":"DISTINCT_SIMFINID_DATE_COUNTS_VERIFIED_RESEARCH_ONLY_NOT_PIT",
        "window":{"start":"2024-01-01","end":"2025-09-30"},
        "canonical_eligible":0,
        "historical_SimFinId_CIK_certifications":0,
        "price_adjustment_certifications":0,
        "operational_DB_modified":False,
        "source_file_modified":False,
        "model_training_performed":False,
        "phase25a_prior_candidate_21months":1,
        "source_price_file_SHA256":sha,
        "metrics":{"valid_source_rows":21},
        "candidate_depth_records":[{
            "SimFinId":"101",
            "ticker":"TEST",
            "candidate_CIK_NOT_verified":"0000000101",
            "valid_ohlc_positive_source_adjusted_rows":21,
            "daily_PIT_or_adjustment_certified":False,
        }],
    }),encoding="utf-8")
    monthly={month:{"TEST"} for month in PER_MONTH_KEYS}
    return csv_path,report_path,monthly


class TestPhase25cSimFinFactorTriage(unittest.TestCase):
    def test_21_month_factor_jump_is_research_only(self):
        with TemporaryDirectory() as td:
            root=Path(td)
            source,prior,members=sample(root)
            original=source.read_bytes()
            with patch("scripts.phase25c_simfin_adjustment_factor_triage._monthly_pit",
                       return_value=members):
                a=analyze(source,root,prior)
            self.assertEqual(a["SimFinIds_reviewed"],1)
            self.assertEqual(a["metrics"]["candidate_ids_with_factor_5pct_month_boundary"],1)
            self.assertEqual(a["metrics"]["factor_5pct_boundary_events"],2)
            self.assertEqual(a["metrics"]["candidate_ids_with_factor_5pct_intra_month"],0)
            self.assertEqual(a["independent_split_events_verified"],0)
            self.assertEqual(a["independent_dividend_events_verified"],0)
            self.assertEqual(a["certified_adjusted_prices"],0)
            self.assertEqual(a["canonical_backtest_eligible_securities"],0)
            self.assertFalse(a["database_modified"])
            self.assertEqual(original,source.read_bytes())

    def test_sha256_input_change_blocks(self):
        with TemporaryDirectory() as td:
            root=Path(td)
            source,prior,_=sample(root)
            source.write_text(source.read_text()+"TEST,101,2025-09-30,10,12,9,10,10\n")
            with self.assertRaisesRegex(ValueError,"SIMFIN_SOURCE_SHA256_MISMATCH"):
                analyze(source,root,prior)

    def test_prior_canonical_claim_is_rejected(self):
        with TemporaryDirectory() as td:
            root=Path(td)
            source,prior,_=sample(root)
            data=json.loads(prior.read_text())
            data["canonical_eligible"]=1
            prior.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,"PRIOR_PHASE25B_NOT_RESEARCH_SAFE"):
                analyze(source,root,prior)

    def test_phase25b_qualified_price_counts_must_match(self):
        with TemporaryDirectory() as td:
            root=Path(td)
            source,prior,members=sample(root)
            data=json.loads(prior.read_text())
            data["candidate_depth_records"][0]["valid_ohlc_positive_source_adjusted_rows"]=22
            prior.write_text(json.dumps(data))
            with patch("scripts.phase25c_simfin_adjustment_factor_triage._monthly_pit",
                       return_value=members):
                with self.assertRaisesRegex(ValueError,"PHASE25B_QUALIFIED_SOURCE_ROWS_CHANGED"):
                    analyze(source,root,prior)

    def test_monthly_listing_window_mismatch_fails(self):
        with TemporaryDirectory() as td:
            root=Path(td)
            source,prior,members=sample(root)
            del members["2025-09"]
            with patch("scripts.phase25c_simfin_adjustment_factor_triage._monthly_pit",
                       return_value=members):
                with self.assertRaisesRegex(ValueError,"MONTHLY_SOURCE_ARCHIVE_WINDOW_MISMATCH"):
                    analyze(source,root,prior)


if __name__=="__main__":
    unittest.main()
