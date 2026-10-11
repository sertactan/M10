"""Acceptance tests for S15.3 route and dated-source hard gates."""
import copy
import unittest
from pathlib import Path
import json

from app.scoring_v13_s15_gate import audit_report, audit_stock, market_cap_candidate

REPORT = Path.home() / "AppData/Local/S153ResearchTerminal/runtime/scoring_completion/v2_audit2/report.json"


class S15GateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not REPORT.is_file():
            raise unittest.SkipTest("Private five-issuer report unavailable")
        cls.raw = REPORT.read_bytes()
        cls.seal = Path(str(REPORT) + ".sha256").read_bytes()
        cls.report = json.loads(cls.raw)

    def test_real_five_issuer_source_and_no_promotion(self):
        result = audit_report(self.raw, self.seal)
        self.assertEqual(result["dated_market_cap_candidates"], 5)
        self.assertEqual(result["new_accepted_S15_3_scores"], 0)
        self.assertTrue(all(r["v12"]["additional_essential_legs_to_70_pct"] >= 2 for r in result["stocks"]))
        self.assertTrue(all(len(r["v14"]["missing_13_feature_inputs"]) == 13 for r in result["stocks"]))
        self.assertTrue(all(r["v141"]["V12_READY"] is False for r in result["stocks"]))

    def test_seal_and_route_coverage_tamper_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "ORIGINAL_REPORT_SEAL_CHANGED"):
            audit_report(self.raw + b" ", self.seal)
        changed = copy.deepcopy(self.report["stocks"][0])
        m = next(m for m in changed["models"] if m["model"] == "S15.3 V1.2")
        m["evidence"]["result"]["components"]["ROUTE_ESSENTIAL_COVERAGE"] = 80
        with self.assertRaisesRegex(ValueError, "ORIGINAL_ROUTE_COVERAGE_CHANGED"):
            audit_stock(changed)

    def test_market_cap_timing_and_existing_crosscheck(self):
        stock = copy.deepcopy(self.report["stocks"][0])
        candidate = market_cap_candidate(stock)
        self.assertEqual(candidate["status"], "DATED_RESEARCH_CANDIDATE_ONLY")
        self.assertIsNone(candidate["destination_supported_mc"])
        stock["features"]["SHARES_OUTSTANDING_DATED"]["available_at"] = "2027-01-01T00:00:00+00:00"
        with self.assertRaisesRegex(ValueError, "PRICE_SHARE_SOURCE_TIME_INCONSISTENT"):
            market_cap_candidate(stock)


if __name__ == "__main__":
    unittest.main()
