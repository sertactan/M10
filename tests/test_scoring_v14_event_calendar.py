"""Independent boundary checks for the V14 scheduled-date evidence gate."""
from datetime import date
import unittest

from app.scoring_v14_event_calendar import audit_calendar, prior_scheduled_sessions, scheduled_open
from scripts.scoring_v14_event_audit import OUT, run


class EventCalendarTests(unittest.TestCase):
    def test_nasdaq_holiday_and_twenty_prior_dates(self):
        self.assertFalse(scheduled_open(date(2026, 9, 7)))
        self.assertFalse(scheduled_open(date(2026, 10, 10)))
        self.assertTrue(scheduled_open(date(2026, 10, 9)))
        dates = prior_scheduled_sessions(date(2026, 10, 9))
        self.assertEqual(len(dates), 20)
        self.assertEqual((dates[0], dates[-1]), (date(2026, 9, 11), date(2026, 10, 8)))
        self.assertNotIn(date(2026, 9, 7), dates)

    def test_no_schedule_substitution_for_same_clock_bars(self):
        source = {
            "schema": "V13_S16_EA_OFFLINE_SOURCE_GATE_V1", "ticker": "INOD",
            "verified_alerts": 0, "S16_EA_score": None,
            "max_prior_same_clock_dates_for_latest_session": 4,
            "ET_dates": [f"2026-10-0{d}" for d in range(5, 10)],
        }
        row = audit_calendar(source)
        self.assertEqual(len(row["required_20_prior_scheduled_sessions"]), 20)
        self.assertEqual(len(row["source_covered_prior_sessions"]), 4)
        self.assertEqual(len(row["missing_prior_scheduled_sessions"]), 16)
        self.assertFalse(row["same_clock_baseline_accepted"])
        self.assertFalse(row["historical_bar_available_at_verified"])
        self.assertFalse(row["historical_news_first_public_and_provider_arrival_verified"])
        self.assertIsNone(row["S16_EA_score"])
        self.assertEqual(row["verified_alerts"], 0)

    def test_closed_observation_or_promoted_alert_rejected(self):
        source = {
            "schema": "V13_S16_EA_OFFLINE_SOURCE_GATE_V1", "ticker": "INOD",
            "verified_alerts": 0, "S16_EA_score": None,
            "max_prior_same_clock_dates_for_latest_session": 4,
            "ET_dates": [f"2026-10-0{d}" for d in range(5, 10)],
        }
        source["ET_dates"][0] = "2026-10-04"
        with self.assertRaisesRegex(ValueError, "SOURCE_BAR_ON_NASDAQ_CLOSED_DATE"):
            audit_calendar(source)
        source["ET_dates"][0] = "2026-10-05"
        source["verified_alerts"] = 1
        with self.assertRaisesRegex(ValueError, "SOURCE_EVENT_GATE_CHANGED"):
            audit_calendar(source)

    def test_sealed_private_replay_if_available(self):
        if not OUT.is_file():
            self.skipTest("Private original source and V14 receipt unavailable")
        row = run(verify=True)
        self.assertEqual(row["missing_prior_scheduled_sessions"], 16)
        self.assertEqual(row["verified_alerts"], 0)


if __name__ == "__main__":
    unittest.main()
