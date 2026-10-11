"""Real cached S16-EA source replay and look-ahead rejection tests."""
import json
from pathlib import Path
import unittest

from app.scoring_v13_event_gate import audit_sources
from scripts.scoring_v13_event_audit import PROBE, NEWS_REPORT, run


class EventGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        paths = (PROBE / "response.json", PROBE / "receipt.json", PROBE / "bars.json",
                 NEWS_REPORT, Path(str(NEWS_REPORT) + ".sha256"))
        if any(not path.is_file() for path in paths):
            raise unittest.SkipTest("Private original event and minute receipts unavailable")
        cls.raw = [path.read_bytes() for path in paths]

    def test_real_source_shortfall_no_alert(self):
        row = audit_sources(*self.raw)
        self.assertEqual((row["one_minute_rows"], row["derived_five_minute_rows"]), (2126, 218))
        self.assertEqual(len(row["ET_dates"]), 5)
        self.assertEqual(row["max_prior_same_clock_dates_for_latest_session"], 4)
        self.assertEqual(row["minimum_additional_prior_sessions_needed"], 16)
        self.assertEqual(row["SEC_8K_event_candidates"], 10)
        self.assertEqual(row["independently_verified_first_public_events"], 0)
        self.assertEqual(row["verified_alerts"], 0)
        self.assertIsNone(row["S16_EA_score"])

    def test_source_or_derived_bar_tampering_rejected(self):
        changed = self.raw.copy()
        changed[0] += b" "
        with self.assertRaisesRegex(ValueError, "ORIGINAL_INTRADAY_RESPONSE_RECEIPT_CHANGED"):
            audit_sources(*changed)
        changed = self.raw.copy()
        saved = json.loads(changed[2])
        saved["one_minute"][0]["volume"] += 1
        changed[2] = json.dumps(saved).encode()
        with self.assertRaisesRegex(ValueError, "ORIGINAL_INTRADAY_DERIVATION_CHANGED"):
            audit_sources(*changed)

    def test_unreviewed_news_time_cannot_be_promoted(self):
        import hashlib
        changed = self.raw.copy()
        news = json.loads(changed[3])
        inod = next(s for s in news["stocks"] if s["ticker"] == "INOD")
        inod["sec_event_candidates_v3"]["events"][0]["first_publication_at"] = "2026-10-09T13:30:00Z"
        changed[3] = json.dumps(news).encode()
        changed[4] = hashlib.sha256(changed[3]).hexdigest().encode()
        with self.assertRaisesRegex(ValueError, "EVENT_PUBLICATION_STATE_REQUIRES_INDEPENDENT_REVIEW"):
            audit_sources(*changed)

    def test_private_offline_replay(self):
        result = run(verify=True)
        self.assertEqual(result["verified_alerts"], 0)
        self.assertEqual(result["latest_session_max_prior_same_clock"], 4)


if __name__ == "__main__":
    unittest.main()
