import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from scripts.phase25i_real_market_gate_matrix import assess


def fixtures(root):
    db=root/"operational.db"
    with sqlite3.connect(db) as con:
        con.execute("CREATE TABLE universe_snapshot_membership(snapshot_date TEXT, security_id TEXT, source TEXT)")
        con.execute("CREATE TABLE canonical_price_selection(purpose TEXT, security_id TEXT,start_date TEXT,end_date TEXT)")
        con.execute("CREATE TABLE corporate_actions(ex_date TEXT,effective_date TEXT)")
        con.execute("CREATE TABLE security_master(delisted_date TEXT)")
        con.execute("CREATE TABLE wf5_replay_runs(status TEXT)")
        con.execute("CREATE TABLE wf6_walk_forward_runs(status TEXT)")
        con.execute("CREATE TABLE fundamental_facts_source(fact_id TEXT)")
        con.execute("CREATE TABLE canonical_model_features(security_id TEXT)")
    reports=[root/"phase24.json",root/"phase25b.json",root/"phase25h.json"]
    values=[
        {"status":"SIMFIN_ID_TO_CIK_CANDIDATES_ONLY_ZERO_HISTORICAL_ID_CERTIFICATIONS",
         "historical_identity_certifications":0,
         "ticker_only_identity_link_accepted":False,
         "canonical_price_selections_written":0,"model_training_performed":False,
         "simfin_ids_in_window":5307,
         "period":{"start":"2024-01-01","end":"2025-09-30"}},
        {"status":"DISTINCT_SIMFINID_DATE_COUNTS_VERIFIED_RESEARCH_ONLY_NOT_PIT",
         "canonical_eligible":0,"historical_SimFinId_CIK_certifications":0,
         "price_adjustment_certifications":0,
         "operational_DB_modified":False,"model_training_performed":False,
         "phase25a_prior_candidate_21months":3557,
         "window":{"start":"2024-01-01","end":"2025-09-30"}},
        {"status":"15_PRIMARY_REFERENCE_COMPARISONS_RESEARCH_ONLY_PRICE_AND_PIT_NOT_CERTIFIED",
         "source_warning_rows":15,"corporate_action_price_adjustment_certified":0,
         "historical_issuer_CIK_certified":0,"canonical_backtest_eligible_securities":0,
         "walk_forward_backtest_allowed":False,"Learning_V3_allowed":False,
         "production_DB_modified":False,"training_performed":False,
         "reference_count_unique_primary_cash_events":13},
    ]
    for name,val in zip(reports,values):name.write_text(json.dumps(val))
    return db,*reports

class TestPhase25iRealMarketGate(unittest.TestCase):
    def test_empty_canonical_tables_block_real_training(self):
        with TemporaryDirectory() as td:
            root=Path(td)
            db,p24,b,h=fixtures(root)
            before=db.read_bytes()
            r=assess(db,p24,b,h,root/"parquet")
            self.assertFalse(r["pit_backtest_eligible"])
            self.assertFalse(r["walk_forward_executed"])
            self.assertFalse(r["Learning_V3_executed"])
            self.assertEqual(r["counts"]["membership"],(0,0,0))
            self.assertEqual(r["counts"]["canonical_backtest_price"],(0,0))
            self.assertIn("NO_AUTHORITATIVE_ADJUSTED_BACKTEST_PRICE_SELECTION",r["blockers"])
            self.assertIn("HISTORICAL_ISSUER_SHARECLASS_CIK_CROSSWALK_NOT_CERTIFIED",r["blockers"])
            self.assertFalse(r["source_db_modified"])
            self.assertEqual(db.read_bytes(),before)
    def test_forged_phase25h_permission_refused(self):
        with TemporaryDirectory() as td:
            root=Path(td)
            db,p24,b,h=fixtures(root)
            a=json.loads(h.read_text())
            a["Learning_V3_allowed"]=True
            h.write_text(json.dumps(a))
            with self.assertRaisesRegex(ValueError,"PRIOR_CANONICAL_PROVENANCE"):
                assess(db,p24,b,h,root)
    def test_missing_db_does_not_create(self):
        with TemporaryDirectory() as td:
            root=Path(td)
            db,p24,b,h=fixtures(root)
            db.unlink()
            with self.assertRaisesRegex(ValueError,"REAL_OPERATIONAL_DATABASE_MISSING"):
                assess(db,p24,b,h,root)
            self.assertFalse(db.exists())

if __name__=="__main__":
    unittest.main()
