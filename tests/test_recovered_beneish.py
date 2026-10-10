"""All inputs are synthetic; tests do not certify stock scores."""
from datetime import datetime, timezone
import unittest

from app.recovered_quality import compute_quality


AT = datetime(2026, 10, 11, tzinfo=timezone.utc)


def row(metric, value, year, kind):
    return dict(metric=metric, value=value, unit="USD", period_kind=kind,
                period_start=f"{year}-01-01" if kind == "ANNUAL" else None,
                period_end=f"{year}-12-31", form_type="10-K",
                source="SEC_EDGAR", source_ref="https://www.sec.gov/Archives/edgar/data/test",
                accession=f"{year}-TEST", evidence_hash="a1" * 32,
                filing_date="2026-02-01", available_at="2026-02-02T12:00:00+00:00")


def two_years():
    previous = dict(REVENUE=100, ACCOUNTS_RECEIVABLE_NET=10,
                    COST_OF_REVENUE=60, CURRENT_ASSETS=30, PPE_NET=40,
                    ASSETS=100, DEPRECIATION=5, SG_AND_A=12, TOTAL_DEBT=20)
    current = dict(REVENUE=120, ACCOUNTS_RECEIVABLE_NET=12,
                   COST_OF_REVENUE=72, CURRENT_ASSETS=36, PPE_NET=48,
                   ASSETS=120, DEPRECIATION=6, SG_AND_A=14.4, TOTAL_DEBT=24,
                   NET_INCOME=12, OPERATING_CASH_FLOW=12)
    instant = {"ACCOUNTS_RECEIVABLE_NET", "CURRENT_ASSETS", "PPE_NET",
               "ASSETS", "TOTAL_DEBT"}
    return [row(k, v, year, "INSTANT" if k in instant else "ANNUAL")
            for year, group in ((2024, previous), (2025, current))
            for k, v in group.items()]


class BeneishRecoveredTests(unittest.TestCase):
    def test_independent_zero_flags_review_yields_full_synthetic_formula(self):
        outcome = compute_quality(two_years(), AT, forensic_review={
            "review_complete": True, "serious_flags": [], "scope": "SYNTHETIC_TEST"})["B_Q"]
        self.assertEqual(outcome["score"], 100.0)
        self.assertAlmostEqual(outcome["components"]["component_risk"], 0.0)
        self.assertEqual(outcome["components"]["normalization"], "SOURCE_CR_DIVIDED_BY_13")
        self.assertFalse(outcome["canonical_accepted"])
        self.assertEqual(outcome["period"], "2025-12-31")

    def test_absent_serious_flags_review_never_means_zero_flags(self):
        outcome = compute_quality(two_years(), AT)["B_Q"]
        self.assertIsNone(outcome["score"])
        self.assertIn("INDEPENDENT_SERIOUS_FLAGS_REVIEW_COMPLETE", outcome["missing"])

    def test_three_independent_flags_apply_full_interaction(self):
        flags = [{"id": str(i), "source_ref": f"https://www.sec.gov/Archives/test/{i}",
                  "evidence_hash": "ab" * 32} for i in range(3)]
        outcome = compute_quality(two_years(), AT, forensic_review={
            "review_complete": True, "serious_flags": flags, "scope": "SYNTHETIC_TEST"})["B_Q"]
        self.assertAlmostEqual(outcome["score"], 100 * (1 - 1 / 13))
        self.assertEqual(outcome["components"]["interaction_risk"], 1)

    def test_duplicate_flags_or_missing_accounting_keep_na(self):
        duplicated = [{"id": "same", "source_ref": "sec:test", "evidence_hash": "ab" * 32}] * 3
        result = compute_quality(two_years(), AT, forensic_review={
            "review_complete": True, "serious_flags": duplicated})["B_Q"]
        self.assertIsNone(result["score"])
        facts = [r for r in two_years() if r["metric"] != "PPE_NET"]
        result = compute_quality(facts, AT, forensic_review={
            "review_complete": True, "serious_flags": []})["B_Q"]
        self.assertIsNone(result["score"])
        self.assertIn("PPE_T_EXACT_FY", result["missing"])

    def test_future_or_conflicting_raw_facts_are_not_promoted(self):
        facts = two_years()
        future = {**facts[0], "available_at": "2027-01-01T00:00:00+00:00"}
        future_result = compute_quality([future, *facts[1:]], AT, forensic_review={
            "review_complete": True, "serious_flags": []})["B_Q"]
        self.assertIsNone(future_result["score"])
        conflict = {**facts[0], "metric": "REVENUE", "value": 999,
                    "available_at": facts[0]["available_at"]}
        result = compute_quality([*facts, conflict], AT, forensic_review={
            "review_complete": True, "serious_flags": []})["B_Q"]
        self.assertIsNone(result["score"])


if __name__ == "__main__":
    unittest.main()
