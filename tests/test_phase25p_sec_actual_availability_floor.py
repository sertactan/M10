from __future__ import annotations
from datetime import datetime, timezone, timedelta
import unittest
from core.research.sec_publication_gate import OBSERVED_ACCEPTANCES

class TestSECActualAvailabilityFloor(unittest.TestCase):
    def test_exact_three_sec_index_facts_and_UTC_conversion(self):
        by={r.ticker:r for r in OBSERVED_ACCEPTANCES}
        self.assertEqual(len(by),3)
        self.assertEqual(by["HUYA"].sec_accepted_at_utc.isoformat(),"2025-04-17T10:43:22+00:00")
        self.assertEqual(by["TDG"].sec_accepted_at_utc.isoformat(),"2024-11-07T21:05:07+00:00")
        self.assertEqual(by["B"].sec_accepted_at_utc.isoformat(),"2024-10-25T10:47:43+00:00")

    def test_period_end_is_not_public_feature_time(self):
        huya=next(r for r in OBSERVED_ACCEPTANCES if r.ticker=="HUYA")
        self.assertFalse(huya.usable_for_model(
            observed_public_dissemination_at=datetime(2024,12,31,tzinfo=timezone.utc),
            feature_available_at=datetime(2025,4,17,11,0,tzinfo=timezone.utc),
            decision_at=datetime(2025,4,17,12,0,tzinfo=timezone.utc)))

    def test_after_sec_acceptance_still_block_without_public_dissemination(self):
        tdg=next(r for r in OBSERVED_ACCEPTANCES if r.ticker=="TDG")
        self.assertFalse(tdg.usable_for_model(
            observed_public_dissemination_at=None,
            feature_available_at=datetime(2024,11,8,tzinfo=timezone.utc),
            decision_at=datetime(2024,11,10,tzinfo=timezone.utc)))

    def test_only_fully_ordered_real_clocks_can_pass(self):
        tdg=next(r for r in OBSERVED_ACCEPTANCES if r.ticker=="TDG")
        published=datetime(2024,11,7,21,8,tzinfo=timezone.utc)
        feature=datetime(2024,11,8,0,30,tzinfo=timezone.utc)
        decision=datetime(2024,11,8,14,30,tzinfo=timezone.utc)
        self.assertTrue(tdg.usable_for_model(
            observed_public_dissemination_at=published,
            feature_available_at=feature, decision_at=decision))
        self.assertFalse(tdg.usable_for_model(
            observed_public_dissemination_at=published,
            feature_available_at=decision+timedelta(hours=1),
            decision_at=decision))
        self.assertFalse(tdg.usable_for_model(
            observed_public_dissemination_at=published.replace(tzinfo=None),
            feature_available_at=feature,decision_at=decision))

if __name__=="__main__":
    unittest.main()
