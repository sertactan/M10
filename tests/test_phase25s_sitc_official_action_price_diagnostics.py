from contextlib import closing
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from scripts.phase25s_sitc_official_action_price_diagnostics import DOCS, reconcile


def fixture(root:Path, *, omit_spinoff=False):
    db=root/"real_research.sqlite"
    with closing(sqlite3.connect(db)) as con:
        con.execute("CREATE TABLE source_daily_price("
                    "simfin_id TEXT,ticker TEXT,trade_date TEXT,"
                    "source_close REAL,source_adj_close REAL)")
        rows=[
          ("998403","SITC","2024-08-16",10,5),
          ("998403","SITC","2024-08-19",40,20),
          ("998403","SITC","2024-09-30",52,26),
          ("998403","SITC","2024-10-01",40,26),
        ]
        if omit_spinoff:
            rows=rows[:-1]
        con.executemany("INSERT INTO source_daily_price VALUES(?,?,?,?,?)",rows)
        con.commit()
    manifest=root/"manifest.json"
    manifest.write_text(json.dumps({
        "schema":"MERIDYEN_PHASE25Q_VERSIONED_RESEARCH_STAGING_V1",
        "status":"RESEARCH_ONLY_NOT_CANONICAL_PIT",
        "period":{"start":"2024-01-01","end":"2025-09-30"},
        "staging_version":"synthetic_fixture_only",
        "source_price_sha256":"a"*64,
        "month_end_retrieved_after_backtest_window":True,
        "canonical_ready":False,
        "backtest_eligible_securities":0,
        "production_DB_modified":False,
        "staging_db":str(db)
    },indent=2))
    return db,manifest


class TestPhase25sSitcOfficialActions(unittest.TestCase):
    def test_two_true_sec_action_references_with_no_price_pit_promotion(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            db,manifest=fixture(root)
            original=db.read_bytes()
            result=reconcile(manifest)
            self.assertEqual(result["issuer_documented_actions"],2)
            self.assertEqual(result["source_pair_diagnostics_computed"],2)
            split,spin=result["actions"]
            self.assertEqual(split["first_split_adjusted_trading_day"],"2024-08-19")
            self.assertEqual(split["old_common_shares_per_new_common_share"],4)
            self.assertEqual(split["new_cusip"],"82981J851")
            self.assertEqual(split["raw_close_ratio"],4)
            self.assertEqual(spin["record_date"],"2024-09-23")
            self.assertEqual(spin["child_common_shares_per_parent_common_share"],2)
            self.assertEqual(spin["spin_child_ticker"],"CURB")
            self.assertEqual(result["canonical_eligible_securities"],0)
            self.assertFalse(result["WF9_executed"])
            self.assertFalse(result["Learning_V3_trained"])
            self.assertFalse(split["independent_adjusted_price_certified"])
            self.assertEqual(db.read_bytes(),original)

    def test_missing_trade_price_keeps_research_only(self):
        with TemporaryDirectory() as tmp:
            db,manifest=fixture(Path(tmp),omit_spinoff=True)
            r=reconcile(manifest)
            self.assertEqual(r["source_pair_diagnostics_computed"],1)
            self.assertFalse(r["actions"][1]["source_pair_complete"])
            self.assertEqual(r["canonical_eligible_securities"],0)

    def test_vendor_canonical_flag_rejected(self):
        with TemporaryDirectory() as tmp:
            db,manifest=fixture(Path(tmp))
            data=json.loads(manifest.read_text())
            data["canonical_ready"]=True
            manifest.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,"SOURCE_DATA_IS_NOT_UNCERTIFIED_RESEARCH_STAGE"):
                reconcile(manifest)

    def test_colliding_ticker_not_assumed_same_security(self):
        with TemporaryDirectory() as tmp:
            db,manifest=fixture(Path(tmp))
            with closing(sqlite3.connect(db)) as con:
                con.execute("UPDATE source_daily_price SET simfin_id='000OTHER' "
                            "WHERE trade_date='2024-08-19'")
                con.commit()
            with self.assertRaisesRegex(ValueError,"SITC_TICKER_COLLISION_DIFFERENT_SIMFIN_ID"):
                reconcile(manifest)


if __name__=="__main__":
    unittest.main()
