"""Synthetic evidence only: never use these financial amounts as stock scores."""

from copy import deepcopy
from datetime import datetime, timezone
import math
import unittest

from app.personal_research.beneish_assessed import analyze_beneish, RISK_LEGS
from app.recovered_beneish import calculate_beneish
from app.recovered_quality import compute_quality


PREV = {"REVENUE": 100, "ACCOUNTS_RECEIVABLE_NET": 10,
        "COST_OF_REVENUE": 60, "CURRENT_ASSETS": 30, "PPE_NET": 40,
        "ASSETS": 100, "DEPRECIATION": 5, "SG_AND_A": 12, "TOTAL_DEBT": 20}
CURR = {"REVENUE": 130, "ACCOUNTS_RECEIVABLE_NET": 20,
        "COST_OF_REVENUE": 90, "CURRENT_ASSETS": 35, "PPE_NET": 45,
        "ASSETS": 140, "DEPRECIATION": 6, "SG_AND_A": 18,
        "TOTAL_DEBT": 30, "NET_INCOME": 16, "OPERATING_CASH_FLOW": 9}
INSTANT = {"ACCOUNTS_RECEIVABLE_NET", "CURRENT_ASSETS", "PPE_NET", "ASSETS", "TOTAL_DEBT"}
REVIEW = {"review_complete": True, "serious_flags": [], "scope": "SYNTHETIC_TEST_REVIEW"}


def row(metric, value, year, **changes):
    kind = "INSTANT" if metric in INSTANT else "ANNUAL"
    original = dict(metric=metric, value=value, unit="USD", period_kind=kind,
                    period_start=f"{year}-01-01" if kind == "ANNUAL" else None,
                    period_end=f"{year}-12-31", form_type="10-K", source="SEC_EDGAR",
                    source_ref=f"https://www.sec.gov/Archives/edgar/data/1234/{year}/data.htm",
                    accession=f"1234-{year}", evidence_hash=f"{year % 256:02x}" * 32,
                    filing_date=f"{year + 1}-02-01",
                    available_at=f"{year + 1}-02-02T12:00:00+00:00", ticker="TEST")
    original.update(changes)
    return original


def two_years():
    return [row(metric, value, year) for year, amounts in ((2024, PREV), (2025, CURR))
            for metric, value in amounts.items()]


def evaluate(facts=None, review=REVIEW):
    return analyze_beneish(two_years() if facts is None else facts,
                           "2025-12-31", "2025-01-01", forensic_review=review)


class AssessedBeneishTests(unittest.TestCase):
    def test_all_seven_frozen_ratios_risks_and_original_score(self):
        facts = two_years()
        result = evaluate(facts)
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(result["numeric_result_type"], "FROZEN_EXACT")
        self.assertEqual(result["original_status"], "CALCULATED")
        self.assertEqual(result["calculated_risks"], 7)
        self.assertFalse(result["canonical_accepted"])
        self.assertEqual(result["missing"], [])
        self.assertTrue(all(result["ratios"][leg] is not None for leg in RISK_LEGS))
        self.assertTrue(all(0 <= result["risks"][leg] <= 1 for leg in RISK_LEGS))
        self.assertEqual(len(result["results"]), 7)
        self.assertEqual(result["components"], result["results"])
        score, original, _, missing = calculate_beneish(facts, "2025-12-31", "2025-01-01", REVIEW)
        self.assertEqual(missing, [])
        self.assertAlmostEqual(result["score"], score)
        self.assertEqual(result["ratios"], {leg: original["ratios"][leg] for leg in RISK_LEGS})
        self.assertEqual(result["risks"], original["risks"])
        self.assertAlmostEqual(result["sales_growth_index"], 1.3)
        self.assertEqual(len(result["receipt_sha256"]), 64)
        self.assertEqual(result["receipt_sha256"], evaluate(deepcopy(facts))["receipt_sha256"])
        self.assertGreaterEqual(len(result["source_evidence"]["source_rows"]), 20)

    def test_complete_frozen_matches_compute_quality_wrapper(self):
        original = compute_quality(two_years(), datetime(2026, 10, 12, tzinfo=timezone.utc),
                                   forensic_review=REVIEW)["B_Q"]
        self.assertAlmostEqual(evaluate()["score"], original["score"])
        self.assertEqual(original["components"]["normalization"], "SOURCE_CR_DIVIDED_BY_13")

    def test_missing_depreciation_and_total_debt_preserve_five_risks(self):
        rows = [r for r in two_years() if r["metric"] not in {"DEPRECIATION", "TOTAL_DEBT"}]
        result = evaluate(rows)
        self.assertIsNone(result["score"])
        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual(result["numeric_result_type"], "COMPONENT_RISKS_ONLY")
        self.assertEqual(result["calculated_risks"], 5)
        self.assertIsNone(result["risks"]["DEPI"])
        self.assertIsNone(result["risks"]["LVGI"])
        self.assertIn("DEP_T_EXACT_FY", result["missing"])
        self.assertIn("DEBT_PREV_EXACT_FY", result["missing"])
        self.assertAlmostEqual(result["risks"]["TATA"], .5)
        self.assertIsNone(result["interaction_risk"])

    def test_missing_forensic_review_never_defaults_to_zero_flags(self):
        result = evaluate(review=None)
        self.assertEqual(result["calculated_risks"], 7)
        self.assertEqual(result["status"], "PARTIAL")
        self.assertIsNone(result["score"])
        self.assertIn("INDEPENDENT_SERIOUS_FLAGS_REVIEW_COMPLETE", result["missing"])
        self.assertIsNone(result["interaction_risk"])

    def test_malformed_forensic_hash_and_unhashable_flag_fail_closed(self):
        invalid_reviews = [
            {"review_complete": True, "serious_flags": [
                {"id": "flag1", "source_ref": "sec:test", "evidence_hash": "nothex" * 10 + "zzzz"}]},
            {"review_complete": True, "serious_flags": [
                {"id": ["unexpected", "list"], "source_ref": "sec:test", "evidence_hash": "ab" * 32}]},
        ]
        for review in invalid_reviews:
            with self.subTest(review=review):
                result = evaluate(review=review)
                self.assertIsNone(result["score"])
                self.assertEqual(result["calculated_risks"], 7)
                self.assertIn("INDEPENDENT_SERIOUS_FLAGS_REVIEW_COMPLETE", result["missing"])

    def test_independent_flags_apply_only_original_interaction(self):
        review = dict(review_complete=True, scope="SYNTHETIC_TEST_REVIEW",
                      serious_flags=[dict(id=str(i), source_ref=f"sec:test:{i}",
                                          evidence_hash="ab" * 32) for i in range(3)])
        baseline, flagged = evaluate(), evaluate(review=review)
        self.assertEqual(flagged["interaction_risk"], 1.0)
        self.assertAlmostEqual(flagged["score"], baseline["score"] - 100 / 13)

    def test_zero_over_zero_debt_is_explicitly_unresolved(self):
        facts = two_years()
        for fact in facts:
            if fact["metric"] == "TOTAL_DEBT":
                fact["value"] = 0
        result = evaluate(facts)
        self.assertEqual(result["calculated_risks"], 6)
        self.assertIsNone(result["score"])
        self.assertIsNone(result["ratios"]["LVGI"])
        self.assertIn("SPEC_EDGE_CASE_ZERO_OVER_ZERO", result["results"]["LVGI"]["missing"])
        self.assertNotEqual(result["risks"]["LVGI"], 0)

    def test_zero_gross_margin_denominator_invalidates_only_gmi(self):
        facts = two_years()
        for fact in facts:
            if fact["metric"] == "COST_OF_REVENUE" and fact["period_end"] == "2025-12-31":
                fact["value"] = 130
        result = evaluate(facts)
        self.assertEqual(result["calculated_risks"], 6)
        self.assertIsNone(result["ratios"]["GMI"])
        self.assertIn("VALID_POSITIVE_BENEISH_DENOMINATORS", result["missing"])

    def test_mixed_da_tag_cannot_be_promoted_to_pure_depreciation(self):
        facts = [r for r in two_years() if r["metric"] != "DEPRECIATION"]
        facts += [row("DEPRECIATION_AND_AMORTIZATION", value, year)
                  for year, value in ((2024, 5), (2025, 6))]
        result = evaluate(facts)
        self.assertEqual(result["calculated_risks"], 6)
        self.assertIsNone(result["risks"]["DEPI"])
        self.assertIn("DEP_T_EXACT_FY", result["missing"])
        facts[-1]["metric"] = "DEPRECIATION"
        facts[-1]["original_metric"] = "DEPRECIATION_AND_AMORTIZATION"
        facts[-1]["scenario_provenance"] = {"id": "bad", "basis": "cannot assert pure DEP"}
        result = evaluate(facts)
        self.assertIsNone(result["risks"]["DEPI"])
        self.assertIn("COMBINED_D_AND_A_IS_NOT_PURE_DEPRECIATION",
                      [r["reason"] for r in result["source_evidence"]["rejected_rows"]])

    def test_debt_proxy_tag_is_not_total_debt(self):
        facts = [r for r in two_years() if r["metric"] != "TOTAL_DEBT"]
        facts += [row("LONG_TERM_DEBT", value, year)
                  for year, value in ((2024, 20), (2025, 30))]
        result = evaluate(facts)
        self.assertIsNone(result["risks"]["LVGI"])
        self.assertIn("DEBT_T_EXACT_FY", result["missing"])

    def test_reject_sources_without_hash_dates_accession_and_official_host(self):
        bad_fields = [dict(source="INFERRED"), dict(source_ref="https://sec.gov.evil.test/x"),
                      dict(evidence_hash="none"), dict(accession=""),
                      dict(available_at="2025-03-02T01:00:00"),
                      dict(period_kind="QUARTER"), dict(unit="JPY"),
                      dict(form_type="10-Q"), dict(value=math.nan)]
        for changes in bad_fields:
            with self.subTest(changes=changes):
                facts = two_years()
                facts[0] = {**facts[0], **changes}
                result = evaluate(facts)
                self.assertIsNone(result["score"])
                self.assertIsNone(result["risks"]["DSRI"] if facts[0]["metric"] == "REVENUE"
                                  else result["score"])
                self.assertGreaterEqual(len(result["source_evidence"]["rejected_rows"]), 1)

    def test_alternate_local_source_requires_specific_scenario_provenance(self):
        facts = two_years()
        facts[0]["source"] = "SEC_EDGAR_LOCAL_ARCHIVE_ACCEPTED_UNVERIFIED"
        facts[0]["source_ref"] = "local-sec:1234"
        result = evaluate(facts)
        self.assertIsNone(result["score"])
        self.assertIn("ALTERNATE_SOURCE_REQUIRES_SCENARIO_PROVENANCE",
                      [row["reason"] for row in result["source_evidence"]["rejected_rows"]])
        facts[0]["scenario_provenance"] = {
            "id": "local-official-archive", "basis": "offline copy of identified SEC accession"}
        result = evaluate(facts)
        self.assertEqual(result["calculated_risks"], 7)
        self.assertIsNotNone(result["score"])
        self.assertEqual(result["status"], "SCENARIO_COMPLETE")
        self.assertEqual(result["numeric_result_type"], "FROZEN_FORMULA_ON_SOURCE_SCENARIO")
        self.assertIn(facts[0]["scenario_provenance"], result["source_evidence"]["scenarios"])
        self.assertFalse(result["canonical_accepted"])

    def test_same_snapshot_conflicts_cannot_be_silently_selected(self):
        facts = two_years()
        contradictory = {**facts[0], "value": 999}
        result = evaluate([*facts, contradictory])
        self.assertIsNone(result["score"])
        self.assertIn("SALES_PREV_CONFLICTING_EVIDENCE", result["missing"])
        self.assertIsNone(result["ratios"]["DSRI"])

    def test_noncontiguous_periods_fail_closed(self):
        result = analyze_beneish(two_years(), "2025-12-31", "2025-02-01", REVIEW)
        self.assertIsNone(result["score"])
        self.assertEqual(result["calculated_risks"], 0)
        self.assertIn("CONTIGUOUS_PRIOR_FISCAL_YEAR", result["missing"])

    def test_mixed_issuer_raises_instead_of_cross_company_ratios(self):
        rows = two_years()
        rows[0]["ticker"] = "OTHER"
        with self.assertRaisesRegex(ValueError, "Mixed-issuer"):
            evaluate(rows)


if __name__ == "__main__":
    unittest.main()
