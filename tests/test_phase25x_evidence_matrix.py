"""Synthetic fail-closed checks; never opens the user's operational DB."""
import sqlite3
import unittest

from scripts.phase25x_evidence_matrix import ORDER, SEC_ANCHORS, audit


class EvidenceMatrixTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.executescript("""
            CREATE TABLE security_master(security_id TEXT, ticker TEXT, cik TEXT, exchange TEXT,
                security_type TEXT, delisted_date TEXT);
            CREATE TABLE fundamental_facts_source(security_id TEXT, period_end TEXT,
                accession_number TEXT, accepted_at TEXT, available_at TEXT);
        """)
        self.w = {"schema": "MERIDYEN_PHASE25W_RESEARCH_PILOT_FAIL_CLOSED_V1",
                  "research_only_pilot_selected": 25, "conflict_rows": 464,
                  "conflict_rows_canonically_resolved": 0, "canonical_accepted_securities_proven": 0,
                  "conflict_quarantine_rows": [{"conflicting_company_identity_quarantined": True} for _ in range(464)],
                  "period": {"start": "2024-01-01", "end": "2025-09-30"},
                  "pilot_candidates": [{"ticker": t, "simfin_id": str(i), "source_price_rows": 438,
                                        "months_with_ticker_source_listing": 21}
                                       for i, t in enumerate(ORDER)] +
                                      [{"ticker": "OTHER" + str(i), "simfin_id": str(i + 100),
                                        "source_price_rows": 438, "months_with_ticker_source_listing": 21}
                                       for i in range(17)]}
        self.p24 = {"candidate_records": [{"ticker_strings": [t], "SimFinId": str(i),
                                             "candidate_CIKs_NOT_verified": [SEC_ANCHORS[t][0]]}
                                            for i, t in enumerate(ORDER)]}
        for t in ORDER:
            cik, accession, _, _ = SEC_ANCHORS[t]
            self.db.execute("INSERT INTO security_master VALUES(?,?,?,?,?,?)", (t, t, cik, "NASDAQ", None, None))
            self.db.execute("INSERT INTO fundamental_facts_source VALUES(?,?,?,?,?)",
                            (t, "2024-12-31", accession, None, "2025-03-14T00:00:00+00:00"))

    def tearDown(self):
        self.db.close()

    def test_public_anchor_does_not_promote_research(self):
        report = audit(self.w, self.p24, self.db)
        self.assertEqual(report["selected_from_phase25w"], 8)
        self.assertEqual(report["canonical_accepted_securities_proven"], 0)
        self.assertEqual(report["phase25w_conflict_rows_quarantined"], 464)
        self.assertEqual(report["wf9_status"], "BLOCKED")
        self.assertTrue(all(r["overall"] == "BLOCKED" and not r["canonical_admitted"] for r in report["candidates"]))
        self.assertEqual(report["candidates"][0]["gate_status"]["sec_publication_and_feature_available_at"], "PARTIAL")

    def test_missing_anchor_fails_closed(self):
        self.db.execute("DELETE FROM fundamental_facts_source WHERE security_id='BRLT'")
        report = audit(self.w, self.p24, self.db)
        self.assertEqual(report["candidates"][0]["gate_status"]["sec_publication_and_feature_available_at"], "BLOCKED")

    def test_identity_mismatch_rejected(self):
        self.db.execute("UPDATE security_master SET cik='9999999999' WHERE ticker='BRLT'")
        with self.assertRaisesRegex(ValueError, "CIK/security binding mismatch"):
            audit(self.w, self.p24, self.db)

    def test_conflict_quarantine_break_rejected(self):
        self.w["conflict_rows_canonically_resolved"] = 1
        with self.assertRaisesRegex(ValueError, "quarantine"):
            audit(self.w, self.p24, self.db)


if __name__ == "__main__":
    unittest.main()
