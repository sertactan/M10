"""Phase25W synthetic regression: does not use any proprietary local prices."""
import json
from pathlib import Path
import sqlite3
from contextlib import closing
from tempfile import TemporaryDirectory
import unittest

from scripts.phase25w_research_pit_pilot import assess, STRONG_CONFLICTS


def fixture(root):
    root = Path(root)
    db = root / "research_pit.sqlite"
    with closing(sqlite3.connect(db)) as c:
        c.executescript("""
            CREATE TABLE source_daily_price(
                simfin_id TEXT, ticker TEXT, trade_date TEXT,
                listed_in_same_month_end_archive INTEGER,
                source_adjustment_certified INTEGER,
                historical_security_identity_certified INTEGER);
            CREATE TABLE candidate_gate(
                simfin_id TEXT, ticker TEXT, priority TEXT,
                missing_evidence TEXT, canonical_approved INTEGER);
            CREATE TABLE candidate_identity(historical_CIK_identity_certified INTEGER);
            CREATE TABLE monthly_research_membership(month_end TEXT,ticker TEXT);
            INSERT INTO candidate_identity VALUES (0);
            INSERT INTO candidate_gate VALUES ('1','AAA','P1','PIT',0);
            INSERT INTO candidate_gate VALUES ('2','BBB','P2','PIT',0);
            INSERT INTO candidate_gate VALUES ('3','B','P1','PIT',0);
            INSERT INTO monthly_research_membership VALUES ('2024-01-31','AAA');
            INSERT INTO monthly_research_membership VALUES ('2024-02-29','BBB');
            INSERT INTO source_daily_price VALUES ('1','AAA','2024-01-30',1,0,0);
            INSERT INTO source_daily_price VALUES ('1','AAA','2024-01-31',1,0,0);
            INSERT INTO source_daily_price VALUES ('2','BBB','2024-01-30',0,0,0);
            INSERT INTO source_daily_price VALUES ('3','B','2024-01-30',0,0,0);
        """)
    market = root / "operational.db"
    with closing(sqlite3.connect(market)) as c:
        c.executescript("""
            CREATE TABLE universe_snapshot_membership(snapshot_date TEXT);
            CREATE TABLE canonical_price_selection(purpose TEXT,start_date TEXT,end_date TEXT);
            CREATE TABLE corporate_actions(event_id TEXT);
        """)
    manifest = {
        "schema": "MERIDYEN_PHASE25Q_VERSIONED_RESEARCH_STAGING_V1",
        "status": "RESEARCH_ONLY_NOT_CANONICAL_PIT",
        "period": {"start": "2024-01-01", "end": "2025-09-30"},
        "month_end_snapshots": 21,
        "month_end_retrieved_after_backtest_window": True,
        "canonical_ready": False, "backtest_eligible_securities": 0,
        "production_DB_modified": False,
        "staging_version": "a" * 64, "staging_db": str(db),
        "monthly_membership_rows": 2,
        "source_daily_valid_price_rows": 4,
        "source_price_sha256": "b" * 64,
        "phase25k_research_gate_rows": 3,
    }
    names = list(STRONG_CONFLICTS) + ["Z" + str(i) for i in range(23)]
    collisions = [{
        "month_end": f"2024-{i//30+1:02d}-28", "ticker": names[i%30],
        "exchange": "NYSE", "first_issuer_name": "First",
        "second_issuer_name": "Second",
        "conflicting_company_identity_quarantined": True
    } for i in range(464)]
    qa = {
        "schema": "MERIDYEN_PHASE25R_FULL_STAGING_RESEARCH_COVERAGE_QA_V1",
        "status": "21_MONTH_FULL_RESEARCH_SOURCE_COVERAGE_RECONCILED_NOT_CANONICAL",
        "staging_version": manifest["staging_version"],
        "canonical_approved_rows": 0,
        "distinct_monthly_ticker_exchange_keys": 2,
        "price_and_membership_counts": {"source_price_rows": 4},
        "membership_identity_conflict_quarantine": collisions,
        "conflicting_month_ticker_exchange_identity_rows": 464,
        "conflicting_distinct_ticker_strings": 30,
        "conflicting_strong_cohort_tickers": list(STRONG_CONFLICTS),
    }
    mp, qp = root / "manifest.json", root / "qa.json"
    mp.write_text(json.dumps(manifest), encoding="utf8")
    qp.write_text(json.dumps(qa), encoding="utf8")
    return mp, qp, db, market


class Phase25WTest(unittest.TestCase):
    def test_pilot_quarantines_all_464_and_does_not_write_sources(self):
        with TemporaryDirectory() as d:
            mp, qp, stage, market = fixture(d)
            original = (stage.read_bytes(), market.read_bytes())
            out = assess(mp, qp, market, pilot_size=25)
            self.assertEqual(out["conflict_rows"], 464)
            self.assertEqual(len(out["conflict_quarantine_rows"]), 464)
            self.assertEqual(out["conflict_rows_canonically_resolved"], 0)
            self.assertEqual(out["research_only_pilot_selected"], 2)
            self.assertEqual({x["ticker"] for x in out["pilot_candidates"]}, {"AAA", "BBB"})
            self.assertEqual(out["pilot_candidates"][0]["ticker"], "AAA")
            self.assertEqual(out["canonical_accepted_securities_proven"], 0)
            self.assertEqual(out["operational_db_observation"]["historical_membership_rows"], 0)
            self.assertEqual(out["operational_db_observation"]["backtest_adjusted_selections"], 0)
            self.assertEqual((stage.read_bytes(), market.read_bytes()), original)

    def test_missing_market_is_unknown_not_zero(self):
        with TemporaryDirectory() as d:
            mp, qp, _, _ = fixture(d)
            out = assess(mp, qp, Path(d) / "notfound.sqlite", pilot_size=1)
            self.assertEqual(out["operational_db_observation"]["status"],
                             "OPERATIONAL_DB_NOT_ACCESSIBLE")
            self.assertIsNone(out["operational_db_observation"]["historical_membership_rows"])
            self.assertEqual(out["research_only_pilot_selected"], 1)

    def test_missing_conflict_fails_closed(self):
        with TemporaryDirectory() as d:
            mp, qp, _, market = fixture(d)
            data = json.loads(qp.read_text(encoding="utf8"))
            data["membership_identity_conflict_quarantine"].pop()
            qp.write_text(json.dumps(data), encoding="utf8")
            with self.assertRaisesRegex(ValueError, "464_CONFLICTS"):
                assess(mp, qp, market)

    def test_stage_version_mismatch_fails_closed(self):
        with TemporaryDirectory() as d:
            mp, qp, _, market = fixture(d)
            data = json.loads(qp.read_text(encoding="utf8"))
            data["staging_version"] = "c" * 64
            qp.write_text(json.dumps(data), encoding="utf8")
            with self.assertRaisesRegex(ValueError, "SOURCE_CONTRACT"):
                assess(mp, qp, market)

    def test_upstream_canonical_flags_cannot_be_promoted(self):
        with TemporaryDirectory() as d:
            mp, qp, stage, market = fixture(d)
            with closing(sqlite3.connect(stage)) as c:
                c.execute("UPDATE candidate_gate SET canonical_approved=1 WHERE simfin_id='1'")
                c.commit()
            with self.assertRaisesRegex(ValueError, "UPSTREAM_RESEARCH_ONLY_GUARD_CHANGED"):
                assess(mp, qp, market)

    def test_sitc_report_must_match_stage_version(self):
        with TemporaryDirectory() as d:
            mp, qp, _, market = fixture(d)
            p = Path(d) / "sitc.json"
            p.write_text(json.dumps({
                "schema": "MERIDYEN_PHASE25S_SITC_OFFICIAL_ACTION_SOURCE_PAIR_RESEARCH_V1",
                "research_staging_version": "wrong",
                "canonical_eligible_securities": 0,
                "corporate_action_vendor_adjusted_price_certified": 0,
                "issuer_documented_actions": 2,
            }), encoding="utf8")
            with self.assertRaisesRegex(ValueError, "SITC_REPORT_UNTRUSTED"):
                assess(mp, qp, market, sitc_path=p)


if __name__ == "__main__":
    unittest.main()
