from __future__ import annotations
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from scripts.phase25l_b_fun_official_identity_transitions import assess, EVIDENCE

def fixture(root):
    f=root/"QA.json"
    conflicts=[]
    for i in range(464):
        ticker="B" if i<20 else "FUN" if i<35 else "X"+str(i%28)
        conflicts.append({
            "month_end":"2024-01-31","ticker":ticker,
            "exchange":"NYSE","first_issuer_name":"Issuer A",
            "second_issuer_name":"Issuer B",
            "conflicting_company_identity_quarantined":True,
        })
    f.write_text(json.dumps({
        "schema":"MERIDYEN_PHASE25R_FULL_STAGING_RESEARCH_COVERAGE_QA_V1",
        "status":"21_MONTH_FULL_RESEARCH_SOURCE_COVERAGE_RECONCILED_NOT_CANONICAL",
        "conflicting_month_ticker_exchange_identity_rows":464,
        "conflicting_distinct_ticker_strings":30,
        "membership_identity_conflict_quarantine":conflicts,
        "canonical_approved_rows":0,
        "actual_WF9_executed":False,"actual_Learning_V3_executed":False,
        "production_DB_modified":False,"staging_version":"a"*64}))
    return f

class TestPhase25lBAndFUN(unittest.TestCase):
    def test_four_issuer_refs_and_all_464_keep_quarantine(self):
        with TemporaryDirectory() as td:
            path=fixture(Path(td))
            old=path.read_bytes()
            report=assess(path)
            self.assertEqual(len(EVIDENCE),4)
            self.assertEqual(report["cash_merger_events_with_documented_terms"],1)
            self.assertEqual(report["source_conflicting_identity_rows_total"],464)
            self.assertEqual(report["source_ticker_collision_rows_remaining_quarantined"],464)
            self.assertEqual(report["official_historic_SimFinId_CIK_full_window_certified"],0)
            self.assertEqual(report["delisting_total_returns_certified"],0)
            self.assertEqual(report["canonical_eligible_securities"],0)
            self.assertEqual(report["source_ambiguous_rows_in_B_FUN"],{"B":20,"FUN":15})
            self.assertEqual(path.read_bytes(),old)
    def test_delisted_barnes_cash_and_barrick_new_cusip_are_distinct(self):
        barnes=next(e for e in EVIDENCE if "BARNES" in e["event"])
        barrick=next(e for e in EVIDENCE if "BARRICK" in e["event"])
        self.assertEqual(barnes["date"],"2025-01-27")
        self.assertEqual(barnes["terminal_cash_USD_per_eligible_common_share"],47.5)
        self.assertEqual(barrick["first_trading_day_new_ticker"],"2025-05-09")
        self.assertNotEqual(barnes["source_CIK"],barrick["source_CIK"])
    def test_fun_old_lp_and_new_common_not_same_issuer(self):
        old,new=[e for e in EVIDENCE if e["source_ticker"]=="FUN"]
        self.assertEqual(old["security_class"],"Depositary LP units")
        self.assertEqual(old["old_lp_unit_to_new_Fun_common_ratio"],1.0)
        self.assertEqual(new["former_SIX_common_to_new_FUN_common_ratio"],0.58)
        self.assertNotEqual(old["source_CIK"],new["source_CIK"])
    def test_mismatch_canonical_status_rejected(self):
        with TemporaryDirectory() as td:
            path=fixture(Path(td))
            data=json.loads(path.read_text())
            data["canonical_approved_rows"]=1
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,"QUARANTINE_STATUS_NOT_TRUSTED"):
                assess(path)
if __name__=="__main__":
    unittest.main()
