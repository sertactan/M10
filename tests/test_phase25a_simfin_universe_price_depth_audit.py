import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.phase25a_simfin_universe_price_depth_audit import audit


def _rec(sid, rows, months, label, ciks, tickers=None, exchanges=None):
    return {
        "SimFinId":sid,
        "ticker_strings":tickers or [sid],
        "candidate_CIKs_NOT_verified":ciks,
        "multiple_exchange_listed_calendar_months":exchanges or [],
        "review_class":label,
        "valid_OHLC_positive_adj_close_rows_with_month_end_ticker_overlap":rows,
        "calendar_months_month_end_ticker_overlap":months,
        "calendar_months_price":months,
        "window_price_rows":max(rows,1),
        "certified_historical_SimFinId_CIK":False,
    }


DIRECT="ONE_PRESENT_DAY_SEC_CIK_CANDIDATE_NOT_HISTORICAL_PROOF"
WEAK="ONE_WEAK_PRESENT_DAY_CIK_CANDIDATE_REVIEW"
RISK="TICKER_MULTIPLE_SIMFIN_IDS_REVIEW"
NO_CIK="NO_SEC_CIK_CANDIDATE"


def _fixture(path: Path):
    records=[
        _rec("A",400,21,DIRECT,["0000000101"]),
        _rec("B",200,18,WEAK,["0000000102"]),
        _rec("C",150,21,RISK,["0000000103"]),
        _rec("D",300,21,NO_CIK,[]),
        _rec("E",180,21,WEAK,["0000000104"],tickers=["OLD","NEW"]),
        _rec("F",101,2,WEAK,["0000000105"]),
        _rec("G",90,5,DIRECT,["0000000106"]),
        _rec("H",100,12,WEAK,["0000000107"]),
    ]
    path.write_text(json.dumps({
        "schema":"MERIDYEN_PHASE24_SIMFIN_SEC_CIK_CANDIDATES_V1",
        "status":"SIMFIN_ID_TO_CIK_CANDIDATES_ONLY_ZERO_HISTORICAL_ID_CERTIFICATIONS",
        "period":{"start":"2024-01-01","end":"2025-09-30"},
        "reconciled_phase19_20_21_23":True,
        "historical_identity_certifications":0,
        "ticker_only_identity_link_accepted":False,
        "canonical_price_selections_written":0,
        "original_SEC_or_price_data_modified":False,
        "model_training_performed":False,
        "simfin_ids_in_window":len(records),
        "candidate_records":records,
    }))
    return path


class TestPhase25aPriceDepth(unittest.TestCase):
    def test_separate_preliminary_risky_and_month_depth_cohorts(self):
        with TemporaryDirectory() as d:
            path=_fixture(Path(d)/"source.json")
            before=path.read_bytes()
            r=audit(path)
            m=r["metrics"]
            self.assertEqual(r["SimFinIds_reviewed"],8)
            self.assertEqual(m["at_least_100_valid_adj_overlap_rows"],7)
            self.assertEqual(m["preliminary_single_CIK_100row_not_pit"],5)
            self.assertEqual(m["preliminary_excluding_known_identity_risk_not_pit"],4)
            self.assertEqual(m["review_18months_single_CIK_not_pit"],2)
            self.assertEqual(m["review_21months_single_CIK_not_pit"],1)
            self.assertEqual(m["review_12months_single_CIK_not_pit"],3)
            self.assertEqual(len(r["ambiguous_preliminary_examples"]),1)
            self.assertEqual(r["canonical_backtest_eligible_securities"],0)
            self.assertEqual(r["certified_historical_SimFinId_CIK"],0)
            self.assertFalse(r["database_modified"])
            self.assertEqual(path.read_bytes(),before)

    def test_schema_mismatch_fails_closed(self):
        with TemporaryDirectory() as d:
            path=_fixture(Path(d)/"source.json")
            obj=json.loads(path.read_text())
            obj["historical_identity_certifications"]=1
            path.write_text(json.dumps(obj))
            with self.assertRaisesRegex(ValueError,"PHASE24_PRIOR_AUDIT_NOT_SAFE"):
                audit(path)

    def test_duplicate_simfin_id_fails_closed(self):
        with TemporaryDirectory() as d:
            path=_fixture(Path(d)/"source.json")
            obj=json.loads(path.read_text())
            obj["candidate_records"][1]["SimFinId"]="A"
            path.write_text(json.dumps(obj))
            with self.assertRaisesRegex(ValueError,"DUPLICATE_SIMFIN_ID"):
                audit(path)

    def test_impossible_month_depth_fails_closed(self):
        with TemporaryDirectory() as d:
            path=_fixture(Path(d)/"source.json")
            obj=json.loads(path.read_text())
            obj["candidate_records"][0][
                "calendar_months_month_end_ticker_overlap"]=22
            path.write_text(json.dumps(obj))
            with self.assertRaisesRegex(ValueError,"PRICE_COVERAGE_IMPOSSIBLE"):
                audit(path)


if __name__=="__main__":
    unittest.main()
