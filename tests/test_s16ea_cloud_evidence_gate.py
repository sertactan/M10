import unittest
from scripts.s16ea_cloud_evidence_gate import assess

BAR={"observed_at":"2026-10-08T14:29:00Z","available_at":"2026-10-08T14:29:02Z",
     "source":"EXCHANGE_VERIFIED_FIXTURE","source_ref":"fixture:bar:1","interval_minutes":1}
NEWS={"observed_at":"2026-10-08T14:28:00Z","available_at":"2026-10-08T14:28:05Z",
      "source":"OFFICIAL_NEWS_FIXTURE","source_ref":"fixture:news:1"}
BASE={"ticker":"INOD","route":"NEWS_AT_OPEN","as_of":"2026-10-08T14:30:00Z",
      "intraday_bars":[BAR],"news_events":[NEWS],
      "coverage_verified":True,"historical_baseline_verified":True}

class CloudGateTests(unittest.TestCase):
    def test_input_attestation_does_not_generate_signal_or_s16_scores(self):
        r=assess(BASE)
        self.assertEqual(r["status"],"RESEARCH_INPUT_GATES_PRESENT_ONLY")
        self.assertFalse(r["canonical_scores_computed"])
        self.assertFalse(r["notification_sent"])
        self.assertEqual(r["s16_c"],"INCONCLUSIVE")

    def test_blocks_future_news_leakage(self):
        p=dict(BASE,news_events=[dict(NEWS,available_at="2026-10-08T14:31:00Z")])
        r=assess(p)
        self.assertIn("NEWS_0_FUTURE_LEAKAGE",r["reasons"])

    def test_blocks_missing_intraday_or_baseline(self):
        r=assess(dict(BASE,intraday_bars=[],historical_baseline_verified=False))
        self.assertIn("MISSING_TIMESTAMPED_INTRADAY",r["reasons"])
        self.assertIn("HISTORICAL_BASELINE_UNVERIFIED",r["reasons"])

    def test_blocks_naive_event_timestamp(self):
        p=dict(BASE,intraday_bars=[dict(BAR,observed_at="2026-10-08T14:29:00")])
        r=assess(p)
        self.assertIn("INTRADAY_0_INVALID_TIMESTAMP",r["reasons"])

    def test_zero_pm_requires_full_coverage_not_news(self):
        p=dict(BASE,route="ZERO_PM_BREAKOUT",news_events=[])
        r=assess(p)
        self.assertEqual(r["status"],"RESEARCH_INPUT_GATES_PRESENT_ONLY")
        self.assertFalse(r["is_trade_signal"])

if __name__=="__main__": unittest.main()
