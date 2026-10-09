import hashlib
import json
import calendar
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts.phase25b_simfin_distinct_daily_depth_audit import (
    analyze, cohort, PER_MONTH_KEYS,
)

DIRECT="ONE_PRESENT_DAY_SEC_CIK_CANDIDATE_NOT_HISTORICAL_PROOF"


def fixture(root):
    src=root/"sample.csv"
    rows=["Ticker,SimFinId,Date,Open,High,Low,Close,Adj. Close"]
    dates=[]
    for month in PER_MONTH_KEYS:
        yy,mm=(int(x) for x in month.split("-"))
        cursor=date(yy,mm,1)
        count=0
        while cursor.month==mm and count<20:
            if cursor.weekday()<5:
                dates.append(cursor)
                rows.append(f"EXA,101,{cursor.isoformat()},10,12,9,11,11")
                count+=1
            cursor+=timedelta(days=1)
    # Duplicate known same-day price and one anomalous weekend row.
    rows.append(f"EXA,101,{dates[0].isoformat()},10,12,9,11,11")
    rows.append("EXA,101,2024-01-06,10,12,9,11,11")
    rows.append("NOPE,999,2024-01-06,10,12,9,11,11")
    src.write_text("\n".join(rows)+"\n")
    sha=hashlib.sha256(src.read_bytes()).hexdigest()
    phase24=root/"phase24.json"
    phase24.write_text(json.dumps({
        "schema":"MERIDYEN_PHASE24_SIMFIN_SEC_CIK_CANDIDATES_V1",
        "status":"SIMFIN_ID_TO_CIK_CANDIDATES_ONLY_ZERO_HISTORICAL_ID_CERTIFICATIONS",
        "period":{"start":"2024-01-01","end":"2025-09-30"},
        "source_sha256":sha,
        "reconciled_phase19_20_21_23":True,
        "historical_identity_certifications":0,
        "ticker_only_identity_link_accepted":False,
        "canonical_price_selections_written":0,
        "original_SEC_or_price_data_modified":False,
        "model_training_performed":False,
        "simfin_ids_in_window":1,
        "candidate_records":[{
            "SimFinId":"101",
            "ticker_strings":["EXA"],
            "candidate_CIKs_NOT_verified":["0000000101"],
            "multiple_exchange_listed_calendar_months":[],
            "review_class":DIRECT,
            "valid_OHLC_positive_adj_close_rows_with_month_end_ticker_overlap":422,
            "calendar_months_month_end_ticker_overlap":21,
            "calendar_months_price":21,
            "window_price_rows":422,
            "certified_historical_SimFinId_CIK":False,
        }],
    }))
    phase25a=root/"phase25a.json"
    phase25a.write_text(json.dumps({
        "schema":"MERIDYEN_PHASE25A_SIMFIN_PRICE_DEPTH_RESEARCH_GATE_V1",
        "status":"PHASE25A_RESEARCH_ONLY_SIMFIN_COVERAGE_DEPTH_NOT_CANONICAL",
        "period":{"start":"2024-01-01","end":"2025-09-30"},
        "SimFinIds_reviewed":1,
        "source_SHA256":sha,
        "canonical_backtest_eligible_securities":0,
        "database_modified":False,
        "metrics":{"review_21months_single_CIK_not_pit":1},
    }))
    monthly={m:{"EXA"} for m in PER_MONTH_KEYS}
    return src,phase24,phase25a,monthly


class TestPhase25bRealDates(unittest.TestCase):
    def test_21_month_weekday_duplicate_and_weekend_evidence(self):
        with TemporaryDirectory() as td:
            src,p24,p25,monthly=fixture(Path(td))
            before=src.read_bytes()
            with patch("scripts.phase25b_simfin_distinct_daily_depth_audit._monthly_pit",
                       return_value=monthly):
                report=analyze(src,Path(td),p24,p25)
            counts=report["metrics"]
            self.assertEqual(report["phase25a_prior_candidate_21months"],1)
            self.assertEqual(counts["valid_source_rows"],422)
            self.assertEqual(counts["distinct_valid_dates"],421)
            self.assertEqual(counts["duplicate_valid_id_dates"],1)
            self.assertEqual(counts["weekend_qualified_rows"],1)
            self.assertEqual(counts["ids_with_15_plus_weekdays_in_all_21_months"],1)
            self.assertEqual(counts["ids_with_400_plus_distinct_weekdays"],1)
            self.assertEqual(report["canonical_eligible"],0)
            self.assertFalse(report["operational_DB_modified"])
            self.assertEqual(src.read_bytes(),before)

    def test_source_byte_change_fails_sha(self):
        with TemporaryDirectory() as td:
            src,p24,p25,monthly=fixture(Path(td))
            src.write_text(src.read_text()+"SPOOF,12,2025-01-01,1,1,1,1,1\n")
            with self.assertRaisesRegex(ValueError,"SIMFIN_INPUT_CHANGED_SHA256"):
                analyze(src,Path(td),p24,p25)

    def test_tampered_preliminary_count_blocked(self):
        with TemporaryDirectory() as td:
            src,p24,p25,monthly=fixture(Path(td))
            blob=json.loads(p25.read_text())
            blob["metrics"]["review_21months_single_CIK_not_pit"]=2
            p25.write_text(json.dumps(blob))
            with self.assertRaisesRegex(ValueError,"PHASE24_AND_25A_ELIGIBILITY_COUNTS_CHANGED"):
                cohort(p24,p25)

    def test_row_count_reconciliation_fail_closed(self):
        with TemporaryDirectory() as td:
            src,p24,p25,monthly=fixture(Path(td))
            blob=json.loads(p24.read_text())
            blob["candidate_records"][0][
                "valid_OHLC_positive_adj_close_rows_with_month_end_ticker_overlap"]=421
            p24.write_text(json.dumps(blob))
            with patch("scripts.phase25b_simfin_distinct_daily_depth_audit._monthly_pit",
                       return_value=monthly):
                with self.assertRaisesRegex(ValueError,"PHASE24_ROW_COUNT_MISMATCH"):
                    analyze(src,Path(td),p24,p25)


if __name__=="__main__":
    unittest.main()
