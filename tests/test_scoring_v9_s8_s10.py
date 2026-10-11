"""Original-source V9 numerical contracts: standard-library, no pytest dependency."""
from __future__ import annotations

from copy import deepcopy
import math
import os
import unittest
import zipfile
import json
from pathlib import Path

from app.scoring_v9_s8_s10 import (
    FROZEN_SOURCE_SHA256, dd_five_year_quality, dd_row, dd_year_regression,
    gnp_size, ohlson_components, tca_change, verify_frozen_source,
    crmd_receivables,
)
from app.scoring_v8_s8_s10 import TARGETS, fiscal_ends


class TestV9FrozenS8S10(unittest.TestCase):
    def test_source_sha_pinned(self):
        self.assertEqual(verify_frozen_source(), FROZEN_SOURCE_SHA256)

    def test_original_size_base_and_prior_year(self):
        result = gnp_size(100_000_000, 2025)
        self.assertEqual(result["gnp_previous_calendar_year"], 2024)
        self.assertAlmostEqual(result["gnp_rebased_1968_eq_100"],
                               100*125.496/18.246, places=9)
        self.assertAlmostEqual(result["SIZE"],
                               math.log(100_000_000/(100*125.496/18.246)))
        self.assertFalse(result["historical_as_of_vintage_verified"])
        with self.assertRaises(ValueError):
            gnp_size(1000.0, 2026)

    def test_no_historical_vintage_promotion(self):
        x = ohlson_components(assets=10_000_000, liabilities=8_000_000,
                              ca=4_000_000, cl=3_000_000, net_income=1_000_000,
                              prior_net_income=800_000, ffo=None, balance_year=2025)
        self.assertEqual(x["status"], "MISSING_ORIGINAL_FFO")
        self.assertIsNone(x["score"])
        self.assertIsNone(x["FUTL"])
        self.assertTrue(x["numeric_frozen_ohlson_components"]["SIZE"] > 0)

    def test_true_zero_is_allowed_not_mistaken_for_missing(self):
        result = ohlson_components(assets=10_000_000, liabilities=8_000_000,
                                   ca=4_000_000, cl=3_000_000, net_income=0.0,
                                   prior_net_income=800_000, ffo=0.0, balance_year=2024)
        self.assertEqual(result["numeric_frozen_ohlson_components"]["FUTL"], 0.0)
        self.assertIsNotNone(result["frozen_O"])
        self.assertIsNone(result["score"])

    def test_chin_both_zero_remains_edge_case(self):
        x = ohlson_components(assets=1_000_000, liabilities=300_000, ca=400_000,
                              cl=100_000, net_income=0.0, prior_net_income=0.0,
                              ffo=None, balance_year=2024)
        self.assertEqual(x["status"], "SPEC_EDGE_CASE_CHIN_ZERO_DENOMINATOR")
        self.assertIsNone(x["score"])

    def test_real_frozen_tca_arithmetic(self):
        self.assertEqual(tca_change(ca_t=120, ca_previous=100, cash_t=14,
                                    cash_previous=10, cl_t=70, cl_previous=60,
                                    st_debt_t=8, st_debt_previous=5), 9.0)
        with self.assertRaises(ValueError):
            tca_change(ca_t=120, ca_previous=100, cash_t=14,
                       cash_previous=10, cl_t=70, cl_previous=60,
                       st_debt_t=None, st_debt_previous=5)

    @staticmethod
    def _panel():
        target = dict(ticker="TARGET", sic=7374, accounting_regime="US_GAAP",
                      fiscal_year=2024, membership_source_hash="a"*64,
                      original_10k_source_hash="b"*64,
                      dated_membership_verified=True, original_10k_verified=True,
                      tca=40.0, assets_t=1000.0, assets_previous=1000.0,
                      cfo_previous=31.0, cfo_current=22.0, cfo_next=17.0)
        peers = []
        for i in range(20):
            # Deterministic distinct full-rank synthetic reference (no real-score claims).
            prev = 10.0 + 4.0*i + (i % 3)*8
            curr = 12.0 + (i % 5)*17 + i*i/12
            nxt = 13.0 + (i % 7)*13 + (i*i % 11)
            beta = (0.015, 0.22, 0.33, -0.19)
            tca = 1000*(beta[0] + beta[1]*prev/1000 +
                        beta[2]*curr/1000 + beta[3]*nxt/1000)
            peers.append({**target, "ticker": f"PEER{i:02d}", "cfo_previous": prev,
                          "cfo_current": curr, "cfo_next": nxt, "tca": tca})
        return target, peers

    def test_frozen_dd_four_parameter_regression(self):
        target, peers = self._panel()
        r = dd_year_regression(peers, target)
        self.assertEqual(r["status"], "FROZEN_YEAR_REGRESSION_RESEARCH_DIAGNOSTIC")
        for actual, expected in zip(r["beta"], (0.015, 0.22, 0.33, -0.19)):
            self.assertAlmostEqual(actual, expected, places=8)
        expected = (target["tca"] / 1000 -
                    (0.015 + 0.22*.031 + 0.33*.022 - 0.19*.017))
        self.assertAlmostEqual(r["target_residual"], expected, places=8)
        self.assertIsNone(r["score"])

    def test_reject_short_undated_duplicate_and_wrong_cohort(self):
        target, peers = self._panel()
        self.assertEqual(dd_year_regression(peers[:19], target)["status"],
                         "HISTORICAL_INDUSTRY_YEAR_PEER_PANEL_MISSING")
        mixed = deepcopy(peers)
        mixed[0]["dated_membership_verified"] = False
        self.assertEqual(dd_year_regression(mixed, target)["peer_count"], 19)
        wrong = deepcopy(peers)
        wrong[0]["accounting_regime"] = "OTHER"
        self.assertEqual(dd_year_regression(wrong, target)["peer_count"], 19)
        with self.assertRaisesRegex(ValueError, "DUPLICATE"):
            dd_year_regression(peers + [deepcopy(peers[0])], target)

    def test_singular_regression_fails_closed(self):
        target, peers = self._panel()
        for peer in peers:
            peer.update(cfo_previous=20, cfo_current=20, cfo_next=20)
        r = dd_year_regression(peers, target)
        self.assertEqual(r["status"], "DD_REGRESSION_INPUT_OR_RANK_FAILURE")

    def test_five_year_sigma_and_year_gates(self):
        rows = [dict(status="FROZEN_YEAR_REGRESSION_RESEARCH_DIAGNOSTIC",
                     target_fiscal_year=2020+i, target_residual=i/100)
                for i in range(5)]
        good = dd_five_year_quality(rows)
        self.assertEqual(good["status"], "DD_SIGMA_RESEARCH_DIAGNOSTIC_ONLY")
        self.assertAlmostEqual(good["sigma_population"], math.sqrt(2)/100)
        self.assertIsNone(good["S10"])
        rows[4]["target_fiscal_year"] = 2026
        self.assertIsNone(dd_five_year_quality(rows)["score"])

    def test_normalized_dd_input_rejects_zero_assets(self):
        with self.assertRaises(ValueError):
            dd_row(tca=2, assets_t=0, assets_previous=0,
                   cfo_previous=1, cfo_current=1, cfo_next=1)

    def test_actual_crmd_alternate_receivables_from_pinned_official_cache(self):
        """Read one original SEC member and verify the exact reported 2021 fact."""
        root = os.environ.get("LOCALAPPDATA")
        if not root:
            self.skipTest("Windows local SEC archive unavailable")
        archive = Path(root) / "S153ResearchTerminal/runtime/bulk/sec/companyfacts.zip"
        if not archive.is_file():
            self.skipTest("Pinned offline SEC Companyfacts archive unavailable")
        import hashlib
        with zipfile.ZipFile(archive) as bundle:
            raw = bundle.read("CIK0001410098.json")
        self.assertEqual(hashlib.sha256(raw).hexdigest(), TARGETS["CRMD"]["sha256"])
        gaap = json.loads(raw)["facts"]["us-gaap"]
        years = fiscal_ends(gaap, TARGETS["CRMD"]["fy_end"])
        result = crmd_receivables(gaap, years)
        self.assertEqual(result["FY2021_net_receivables_fallback"]["value"], 45368)
        self.assertEqual(result["FY2021_net_receivables_fallback"]["accession"],
                         "0001213900-22-015852")
        for year in ("2022", "2023"):
            self.assertNotIn("value", result["years"][year]["AccountsReceivableNetCurrent"])
            self.assertNotIn("value", result["years"][year]["AccountsReceivableNet"])
        self.assertFalse(result["accounting_equivalence_to_current_tag_verified"])


if __name__ == "__main__":
    unittest.main()
