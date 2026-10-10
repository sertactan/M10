"""Synthetic-only unit fixtures; actual ticker runs are recorded separately."""
from datetime import datetime, timezone
import unittest
from app.recovered_quality import compute_quality, SOURCE_SHA256

AT = datetime(2026, 10, 11, tzinfo=timezone.utc)


def fact(metric, value, *, start="2025-01-01", end="2025-12-31", kind="ANNUAL", **overrides):
    row = dict(metric=metric, value=value, period_start=start, period_end=end,
               period_kind=kind, unit="USD", source="SEC_EDGAR",
               source_ref="https://data.sec.gov/synthetic-test.json", accession="TEST-ONLY",
               evidence_hash="ab" * 32, form_type="10-K", filing_date="2026-03-01",
               available_at="2026-03-01T12:00:00+00:00")
    return {**row, **overrides}


def fixture():
    return [fact("REVENUE", 100), fact("NET_INCOME", 10),
            fact("OPERATING_CASH_FLOW", 12), fact("CAPEX", 2),
            fact("TOTAL_ASSETS", 100, start=None, kind="INSTANT"),
            fact("TOTAL_ASSETS", 100, start=None, end="2024-12-31", kind="INSTANT")]


class RecoveredQualityTests(unittest.TestCase):
    def test_full_s7_and_s12_independent_reference(self):
        output = compute_quality(fixture(), AT)
        self.assertEqual(output["S7"]["score"], 100)
        self.assertEqual(output["S7"]["components"]["sloan_accrual"], -.02)
        # CCR1.2=100; FCFCR1=90; OCFM12%=65; FCFM10%=65.
        self.assertAlmostEqual(output["S12"]["score"], 84.75)
        for key in ("S7", "S12"):
            self.assertEqual(output[key]["status"], "VERIFIED_DONE")
            self.assertFalse(output[key]["canonical_accepted"])
            self.assertEqual(output[key]["evidence"]["contract_sha256"], SOURCE_SHA256)
            self.assertEqual(len(output[key]["evidence"]["inputs"]), 4)
        self.assertTrue(all(output[k]["score"] is None for k in ("B_Q", "S6", "S11", "S13")))

    def test_repository_assets_metric_alias_preserves_source(self):
        rows = [{**r, "metric": "ASSETS"} if r["metric"] == "TOTAL_ASSETS" else r for r in fixture()]
        result = compute_quality(rows, AT)["S7"]
        self.assertEqual(result["score"], 100)
        self.assertEqual(result["evidence"]["inputs"][2]["metric"], "ASSETS")

    def test_positive_accrual_linear_interpolation(self):
        rows = [r if r["metric"] != "NET_INCOME" else {**r, "value": 19.5} for r in fixture()]
        self.assertAlmostEqual(compute_quality(rows, AT)["S7"]["score"], 62.5)

    def test_missing_asset_boundary_not_substituted(self):
        rows = [r for r in fixture() if r["period_end"] != "2024-12-31"]
        rows.append(fact("TOTAL_ASSETS", 100, start=None, end="2025-01-01", kind="INSTANT"))
        output = compute_quality(rows, AT)
        self.assertIsNone(output["S7"]["score"])
        self.assertIn("TOTAL_ASSETS_FY_START_MINUS_ONE_DAY", output["S7"]["missing"])
        self.assertIsNotNone(output["S12"]["score"])

    def test_future_bad_hash_and_currency_fail_closed(self):
        for override in ({"available_at": "2027-01-01T00:00:00+00:00"},
                         {"evidence_hash": "missing"}, {"unit": "EUR"},
                         {"value": float("nan")}, {"source": "UNKNOWN"}):
            with self.subTest(override=override):
                rows = [{**r, **override} if r["metric"] == "OPERATING_CASH_FLOW" else r for r in fixture()]
                output = compute_quality(rows, AT)
                self.assertIsNone(output["S7"]["score"])
                self.assertIsNone(output["S12"]["score"])

    def test_fiscal_period_mismatch_not_joined(self):
        rows = [{**r, "period_start": "2025-02-01"} if r["metric"] == "CAPEX" else r for r in fixture()]
        self.assertIsNone(compute_quality(rows, AT)["S12"]["score"])

    def test_nonpositive_income_only_partial_not_full(self):
        rows = [{**r, "value": -10} if r["metric"] == "NET_INCOME" else r for r in fixture()]
        result = compute_quality(rows, AT)["S12"]
        self.assertIsNone(result["score"])
        self.assertEqual(result["status"], "PARTIAL")
        self.assertIn("partial_diagnostic_score", result["components"])

    def test_no_silent_same_time_conflict_selection(self):
        rows = fixture() + [fact("CAPEX", 20, accession="OTHER-TEST-ONLY")]
        self.assertIsNone(compute_quality(rows, AT)["S12"]["score"])

    def test_capex_outflow_sign_convention(self):
        rows = [{**r, "value": -2} if r["metric"] == "CAPEX" else r for r in fixture()]
        self.assertEqual(compute_quality(rows, AT)["S12"]["score"], 84.75)

    def test_mixed_issuers_and_naive_asof_rejected(self):
        with self.assertRaises(ValueError):
            compute_quality([fact("REVENUE", 100, ticker="A"), fact("NET_INCOME", 5, ticker="B")], AT)
        with self.assertRaises(ValueError):
            compute_quality(fixture(), datetime(2026, 10, 11))

    def test_missing_never_defaults_to_zero_and_newest_not_backfilled(self):
        self.assertTrue(all(v["score"] is None for v in compute_quality([], AT).values()))
        rows = fixture() + [fact("REVENUE", 200, start="2026-01-01", end="2026-09-30")]
        self.assertIsNone(compute_quality(rows, AT)["S12"]["score"])


if __name__ == "__main__":
    unittest.main()
