"""Synthetic fixture tests only. These are not observed market results."""
import json
import tempfile
import unittest
from pathlib import Path
from scripts.mobile_provider_evidence import (
    SIGNALS, normalize_daily_quote, compare_daily_prices, inventory_s16_evidence, normalize_social_scan,
)
from scripts.s16ea_alert_journal_dryrun import record

ASOF="2026-10-08T20:00:00Z"
FIXTURE={"ticker":"INOD","route":"NEWS_AT_OPEN","as_of":ASOF,
    "intraday_bars":[{"observed_at":"2026-10-08T19:59:00Z",
                       "available_at":"2026-10-08T19:59:05Z",
                       "source":"TEST_SYNTHETIC","source_ref":"mock:bar:1","interval_minutes":1}],
    "news_events":[{"observed_at":"2026-10-08T19:58:00Z",
                    "available_at":"2026-10-08T19:58:05Z",
                    "source":"TEST_SYNTHETIC","source_ref":"mock:news:1"}],
    "coverage_verified":True,"historical_baseline_verified":True}

def fake_evidence():
    return {name:{"value":0.2 if name.endswith("_risk") else 65.0,
        "source":"TEST_SYNTHETIC","source_ref":"mock:"+name,
        "observed_at":"2026-10-08T19:00:00Z",
        "available_at":"2026-10-08T19:01:00Z",
        "pit_verified":True} for name in SIGNALS}

class MobileProviderTests(unittest.TestCase):
    def test_s16_count_and_missing_fails_closed(self):
        self.assertEqual(len(SIGNALS),22)
        r=inventory_s16_evidence("INOD",ASOF,{})
        self.assertEqual(len(r["missing"]),22)
        self.assertEqual(r["s16_e"],"NOT_COMPUTED")
        self.assertFalse(r["canonical_certified"])
        self.assertEqual(r["status"],"BLOCKED_INPUT_GATES")

    def test_fake_complete_evidence_never_claims_canonical(self):
        r=inventory_s16_evidence("INOD",ASOF,fake_evidence())
        self.assertEqual(r["status"],"SOURCE_ASSERTED_READY_NEEDS_INDEPENDENT_AUDIT")
        self.assertFalse(r["canonical_certified"])
        self.assertFalse(r["score_calculated"])

    def test_future_timestamp_and_negative_values_block(self):
        e=fake_evidence()
        e["market_cap_scarcity"]["available_at"]="2026-10-09T00:00:00Z"
        e["dilution_risk"]["value"]=-0.1
        r=inventory_s16_evidence("INOD",ASOF,e)
        self.assertIn("market_cap_scarcity",r["future_or_invalid_dates"])
        self.assertIn("dilution_risk",r["invalid_values"])

    def test_real_time_fabrication_blocked(self):
        q={"status":"OK_UNOFFICIAL_DAILY_BAR","symbol":"INOD",
           "price":61.2,"bar_date":"2026-10-07 00:00:00-04:00",
           "source":"YFINANCE_YAHOO_UNOFFICIAL",
           "retrieved_at_utc":"2026-10-08T23:10:00Z"}
        r=normalize_daily_quote(q,"YFINANCE_YAHOO_UNOFFICIAL")
        self.assertEqual(r["bar_date"],"2026-10-07")
        self.assertFalse(r["real_time_verified"])
        self.assertFalse(r["canonical_eligible"])
        self.assertEqual(r["currency"],"USD_UNVERIFIED")
        self.assertEqual(compare_daily_prices(r,r)["status"],"BLOCKED_CURRENCY_UNVERIFIED")

    def test_openbb_daily_bars_latest_date_not_list_order(self):
        p={"status":"UPSTREAM_FETCH_VERIFIED","symbol":"SPY",
           "provider":"openbb.cboe","retrieved_at":"2026-10-08T22:00:00Z",
           "bars":[{"date":"2026-10-07","close":680.0},
                   {"date":"2026-10-06","close":678.0}]}
        self.assertEqual(normalize_daily_quote(p,"OPENBB_FREE")["daily_close"],680.0)

    def test_social_scan_is_research_only_not_s16(self):
        record={"module":"MERIDYEN_SOCIAL_V5_FREE","ticker":"INOD",
            "source_status":{"bluesky":{"status":"OK","captured":1}},
            "posts":[{"source_url":"https://bsky.app/profile/example/post/abc",
              "created_at":"2026-10-08T18:00:00Z",
              "observed_at":"2026-10-08T18:00:05Z"}]}
        r=normalize_social_scan(record)
        self.assertFalse(r["canonical_eligible"])
        self.assertFalse(r["historical_baseline_verified"])
        self.assertEqual(r["one_shot_posts"],1)
        self.assertEqual(r["s16_e"],"NOT_COMPUTED")

    def test_cboe_no_pit_and_missing_quotes_rejected(self):
        q={"status":"UPSTREAM_FETCH_VERIFIED","symbol":"SPY",
           "provider":"openbb.cboe","retrieved_at":"2026-10-08T22:00:00Z",
           "bars":[{"date":"2026-10-07","close":680.0}]}
        r=normalize_daily_quote(q,"OPENBB_FREE")
        self.assertFalse(r["pit_valid"])
        with self.assertRaises(ValueError):
            normalize_daily_quote({"status":"OPENBB_FREE_BLOCKED"},"OPENBB_FREE")

    def test_dry_run_only_and_duplicate_idempotence(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"research.jsonl"
            dry=record(FIXTURE,p)
            self.assertEqual(dry["status"],"RESEARCH_DRY_RUN")
            self.assertFalse(p.exists())
            persisted=record(FIXTURE,p,dry_run=False)
            self.assertTrue(persisted["recorded"])
            self.assertFalse(persisted["notification_sent"])
            self.assertEqual(record(FIXTURE,p,dry_run=False)["status"],"RESEARCH_DUPLICATE")
            self.assertEqual(len(p.read_text().splitlines()),1)

    def test_invalid_time_never_journaled(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"research.jsonl"
            fake=dict(FIXTURE,as_of="2026-10-08T18:00:00Z")
            self.assertEqual(record(fake,p,dry_run=False)["status"],"BLOCKED")
            self.assertFalse(p.exists())

if __name__=="__main__":
    unittest.main()
