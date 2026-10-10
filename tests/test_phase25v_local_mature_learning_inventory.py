"""Isolated, synthetic SQLite tests: no private M10 data and no mutations."""
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.phase25v_local_mature_learning_inventory import inspect


class Phase25VTest(unittest.TestCase):
    def test_missing_local_dbs_are_unknown_not_zero(self):
        with TemporaryDirectory() as d:
            a = inspect(Path(d) / "missing_market.db", Path(d) / "missing_learning.db", "2026-10-10")
            self.assertEqual(a["status"], "LOCAL_DATABASE_ACCESS_BLOCKED")
            self.assertIsNone(a["native_wf5_labels"]["mature_by_cutoff"])
            self.assertIsNone(a["source_counts"]["wf5_complete_runs"])

    def test_mature_counts_are_distinct_cutoff_aware_and_read_only(self):
        with TemporaryDirectory() as d:
            market, learn = Path(d) / "operational.db", Path(d) / "meridyen_learning.sqlite3"
            with sqlite3.connect(market) as con:
                con.executescript("""
                CREATE TABLE wf5_replay_runs (run_id TEXT, status TEXT);
                CREATE TABLE wf6_walk_forward_runs (run_id TEXT, status TEXT);
                CREATE TABLE wf5_replay_observations (observation_id TEXT);
                INSERT INTO wf5_replay_runs VALUES ('w5','COMPLETE');
                INSERT INTO wf6_walk_forward_runs VALUES ('w6','BLOCKED');
                INSERT INTO wf5_replay_observations VALUES ('a');
                """)
            with sqlite3.connect(learn) as con:
                con.executescript("""
                CREATE TABLE learning_v2_wf5_batches (
                  digest TEXT, run_id TEXT, cutoff TEXT,
                  source_pit_verified INTEGER, mature_count INTEGER);
                CREATE TABLE learning_v2_wf5_mature_labels (
                  digest TEXT, security_id TEXT, signal_date TEXT,
                  label_available_at TEXT, horizon_sessions INTEGER,
                  hit_2x INTEGER, hit_5x INTEGER, hit_10x INTEGER);
                CREATE TABLE learning_v2_research_observations (ticker TEXT);
                INSERT INTO learning_v2_wf5_batches VALUES
                  ('x','w5','2026-10-10',0,2),('y','w5','2026-10-10',0,1);
                INSERT INTO learning_v2_wf5_mature_labels VALUES
                  ('x','AAA','2025-01-02','2026-01-10T14:30:00+00:00',252,1,1,1),
                  ('y','AAA','2025-01-02','2026-01-10T14:30:00+00:00',252,1,1,1),
                  ('x','BBB','2026-01-05','2026-12-10T14:30:00+00:00',252,1,0,0),
                  ('y','CCC','2025-01-02','2025-01-02T14:30:00+00:00',252,1,0,0);
                INSERT INTO learning_v2_research_observations VALUES ('INOD');
                """)
            before = (market.read_bytes(), learn.read_bytes())
            report = inspect(market, learn, "2026-10-10")
            self.assertEqual(report["source_counts"]["wf5_complete_runs"], 1)
            self.assertEqual(report["source_counts"]["wf6_complete_runs"], 0)
            self.assertEqual(report["native_wf5_labels"]["rows"], 4)
            self.assertEqual(report["native_wf5_labels"]["distinct_security_signal_dates"], 3)
            self.assertEqual(report["native_wf5_labels"]["mature_by_cutoff"], 1)
            self.assertEqual(report["native_wf5_labels"]["hit_10x"], 1)
            self.assertEqual(report["native_wf5_labels"]["bad_availability"], 1)
            self.assertEqual(report["native_wf5_labels"]["duplicate_across_batches"], 1)
            self.assertIsNone(report["independently_certified_mature_labels"])
            self.assertEqual(before, (market.read_bytes(), learn.read_bytes()))

    def test_same_path_is_rejected(self):
        with TemporaryDirectory() as d:
            p = Path(d) / "same.db"
            with self.assertRaisesRegex(ValueError, "SOURCE_DATABASES_MUST_BE_DISTINCT"):
                inspect(p, p, "2026-10-10")


if __name__ == "__main__":
    unittest.main()
