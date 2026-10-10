"""Independent synthetic S11 fixtures; no actual issuer score is claimed."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import math
import unittest

from app.recovered_jones import (
    CONTRACT_SHA256, MAX_FISCAL_END_GAP_DAYS, MIN_OTHER_PEERS, compute_s11,
)


AT = datetime(2026, 10, 11, tzinfo=timezone.utc)
ALPHAS = (2.0, .4, .07)


def _fact(metric, value, *, period_end, period_start=None, sid):
    kind = "ANNUAL" if period_start is not None else "INSTANT"
    cik = str(1234000 + int(sid.rsplit("-", 1)[1])).zfill(10)
    return {
        "security_id": sid, "metric": metric, "value": value, "unit": "USD",
        "period_kind": kind, "period_start": period_start, "period_end": period_end,
        "source": "SEC_EDGAR",
        "source_ref": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
        "form_type": "10-K", "accession": "0001104659-26-020655",
        "filing_date": "2026-03-01", "accepted_at": "2026-03-01T12:00:00+00:00",
        "available_at": "2026-03-02T12:00:00+00:00",
        "evidence_hash": "a1" * 32,
    }


def issuer(i, *, target=False):
    sid = f"SYNTHETIC-{i:02d}"
    cik = str(1234000 + i).zfill(10)
    assets_previous = 100 + i * 11
    ppe = 30 + (i * 5 % 13) * 2 + i * .3
    delta_revenue = 10 + (i % 7) * 3 + (i * i % 13)
    current_rev = 100 + i + delta_revenue
    prior_rev = 100 + i
    prev_rec = 7 + i * .2
    curr_rec = prev_rec + 4
    accrual = ALPHAS[0] + ALPHAS[1] * delta_revenue + ALPHAS[2] * ppe
    if target:
        accrual += .04 * assets_previous
    curr_start, curr_end = "2025-01-01", "2025-12-31"
    prev_start, prev_end = "2024-01-01", "2024-12-31"
    facts = [
        _fact("NET_INCOME", 15 + accrual, sid=sid,
              period_start=curr_start, period_end=curr_end),
        _fact("OPERATING_CASH_FLOW", 15, sid=sid,
              period_start=curr_start, period_end=curr_end),
        _fact("REVENUE", current_rev, sid=sid,
              period_start=curr_start, period_end=curr_end),
        _fact("REVENUE", prior_rev, sid=sid,
              period_start=prev_start, period_end=prev_end),
        _fact("ACCOUNTS_RECEIVABLE_NET", curr_rec, sid=sid, period_end=curr_end),
        _fact("ACCOUNTS_RECEIVABLE_NET", prev_rec, sid=sid, period_end=prev_end),
        _fact("PPE_NET", ppe, sid=sid, period_end=curr_end),
        _fact("TOTAL_ASSETS", assets_previous, sid=sid, period_end=prev_end),
    ]
    return {
        "security_id": sid, "cik": cik, "fiscal_year": 2025,
        "period_start": curr_start, "period_end": curr_end,
        "industry": {
            "scheme": "SIC", "code": "7372", "effective_on": "2020-01-01",
            "source": "SEC_EDGAR",
            "source_ref": f"https://data.sec.gov/submissions/CIK{cik}.json",
            "available_at": "2026-03-02T12:00:00+00:00",
            "evidence_hash": "bb" * 32,
        },
        "facts": facts,
    }


def peers(n=20):
    return [issuer(i) for i in range(1, n + 1)]


def target():
    return issuer(29, target=True)


class RecoveredJonesTests(unittest.TestCase):
    def test_contract_source_and_cohort_policy(self):
        self.assertEqual(CONTRACT_SHA256,
                         "53dce841fd5ebdfeb00636f327493be1255ea8b60e6df4eadd921a7098813794")
        self.assertEqual(MIN_OTHER_PEERS, 20)
        self.assertEqual(MAX_FISCAL_END_GAP_DAYS, 45)

    def test_independent_exact_ols_three_coefficients_and_modified_jones(self):
        sample = target()
        result = compute_s11(sample, peers(), AT)
        self.assertEqual(result["status"], "VERIFIED_DONE")
        self.assertEqual(result["components"]["eligible_peer_count"], 20)
        coeffs = result["components"]["OLS_coefficients"]
        for key, expected in zip(("alpha1", "alpha2", "alpha3"), ALPHAS):
            self.assertAlmostEqual(coeffs[key], expected, places=9)
        previous_assets = sample["facts"][-1]["value"]
        delta_rec = sample["facts"][4]["value"] - sample["facts"][5]["value"]
        expected_da = .04 + ALPHAS[1] * delta_rec / previous_assets
        self.assertAlmostEqual(result["components"]["discretionary_accrual"], expected_da)
        self.assertAlmostEqual(result["score"], 100 * (1 - abs(expected_da) / .20))
        self.assertEqual(result["components"]["discretionary_accrual_sign"], "INCOME_INCREASING")
        self.assertEqual(result["components"]["peer_percentile_applied"], False)
        self.assertFalse(result["canonical_accepted"])
        self.assertFalse(result["evidence"]["source_content_hashes_verified"])
        self.assertEqual(result["scope"], "RESEARCH_ONLY_NOT_CANONICAL_PIT")

    def test_no_or_insufficient_peers_never_falls_back_to_zero_ols(self):
        for cohort in (None, [], peers(1), peers(19)):
            with self.subTest(n=len(cohort) if cohort is not None else None):
                result = compute_s11(target(), cohort, AT)
                self.assertIsNone(result["score"])
                self.assertEqual(result["status"], "DATA_MISSING")
                self.assertTrue(result["missing"])
        self.assertIn("ELIGIBLE_INDUSTRY_YEAR_PEERS_LT_20",
                      compute_s11(target(), peers(19), AT)["missing"])

    def test_target_raw_required_and_strict_exact_period(self):
        sample = target()
        sample["facts"] = [r for r in sample["facts"] if r["metric"] != "PPE_NET"]
        result = compute_s11(sample, peers(), AT)
        self.assertIsNone(result["score"])
        self.assertIn("PPE_T_EXACT_PERIOD_MISSING", result["missing"])
        sample = target()
        sample["facts"][0]["period_start"] = "2025-02-01"
        result = compute_s11(sample, peers(), AT)
        self.assertIn("NET_INCOME_T_EXACT_PERIOD_MISSING", result["missing"])

    def test_target_bad_fiscal_year_and_previous_fiscal_revenue(self):
        sample = target()
        sample["fiscal_year"] = 2024
        self.assertIn("VALID_ANNUAL_FISCAL_YEAR_WINDOW",
                      compute_s11(sample, peers(), AT)["missing"])
        sample = target()
        sample["facts"][3]["period_start"] = "2024-03-01"
        self.assertIn("CONTIGUOUS_PREVIOUS_ANNUAL_REVENUE_WINDOW",
                      compute_s11(sample, peers(), AT)["missing"])

    def test_sec_issuer_cik_and_companyfacts_urls_are_identity_bound(self):
        for change in ("cik", "industry_url", "fact_url", "fact_security_id"):
            with self.subTest(change=change):
                sample = target()
                if change == "cik":
                    sample["cik"] = "0000000000"
                elif change == "industry_url":
                    sample["industry"]["source_ref"] = (
                        "https://data.sec.gov/submissions/CIK0001234001.json")
                elif change == "fact_url":
                    sample["facts"][0]["source_ref"] = (
                        "https://data.sec.gov/api/xbrl/companyfacts/CIK0001234001.json")
                else:
                    sample["facts"][0]["security_id"] = "ANOTHER_SECURITY"
                result = compute_s11(sample, peers(), AT)
                self.assertIsNone(result["score"])

    def test_distinct_security_ids_sharing_cik_are_not_independent_peers(self):
        cohort = peers(21)
        cohort[20]["cik"] = cohort[0]["cik"]
        result = compute_s11(target(), cohort, AT)
        self.assertIsNone(result["score"])
        self.assertIn("DUPLICATE_OR_TARGET_INCLUDED_IN_PEERS", result["missing"])

    def test_input_classification_unsupported_types_fail_closed(self):
        for field, value in (("scheme", []), ("code", {"x": "7372"}),
                             ("source_ref", "https://evil.example.com/SEC"),
                             ("available_at", "2027-01-01T01:00:00Z")):
            with self.subTest(field=field):
                sample = target()
                sample["industry"][field] = value
                result = compute_s11(sample, peers(), AT)
                self.assertIsNone(result["score"])
                self.assertIn("DATED_INDUSTRY_CLASSIFICATION", result["missing"])

    def test_source_timestamp_hash_and_currency_fail_closed(self):
        alterations = (
            ("evidence_hash", "spoofed"),
            ("source", "UNKNOWN"),
            ("source_ref", "https://attacker.example.com/companyfacts"),
            ("unit", "JPY"),
            ("accepted_at", "2027-01-01T00:00:00Z"),
            ("available_at", "2027-01-01T00:00:00Z"),
            ("available_at", "2026-02-01T00:00:00Z"),
            ("filing_date", "2027-01-01"),
            ("value", float("nan")),
            ("value", float("inf")),
        )
        for key, value in alterations:
            with self.subTest(key=key, value=value):
                sample = target()
                sample["facts"][0][key] = value
                result = compute_s11(sample, peers(), AT)
                self.assertIsNone(result["score"])
                self.assertIn("NET_INCOME_T_SOURCE_TIME_HASH_INVALID", result["missing"])

    def test_peer_metadata_time_classification_and_year_exclusions(self):
        cases = (
            ("industry", "code", "7373"),
            ("industry", "available_at", "2027-01-01T00:00:00+00:00"),
            ("industry", "evidence_hash", "bad"),
            ("industry", "effective_on", "2026-01-01"),
            ("observation", "fiscal_year", 2024),
            ("observation", "period_end", "2025-09-30"),
        )
        for location, field, value in cases:
            with self.subTest(field=field):
                cohort = peers()
                if location == "industry":
                    cohort[0]["industry"][field] = value
                else:
                    cohort[0][field] = value
                result = compute_s11(target(), cohort, AT)
                self.assertIsNone(result["score"])
                self.assertEqual(result["components"]["eligible_peer_count"], 19)
                self.assertIn("ELIGIBLE_INDUSTRY_YEAR_PEERS_LT_20", result["missing"])

    def test_optional_invalid_peer_excluded_when_20_other_complete(self):
        cohort = peers(21)
        cohort[0]["facts"][0]["evidence_hash"] = "bad"
        result = compute_s11(target(), cohort, AT)
        self.assertIsNotNone(result["score"])
        self.assertEqual(result["components"]["eligible_peer_count"], 20)
        self.assertEqual(result["components"]["excluded_peer_count"], 1)
        self.assertIn("NET_INCOME_T_SOURCE_TIME_HASH_INVALID",
                      result["evidence"]["excluded_peers"][0]["missing"])

    def test_duplicates_fail_even_with_other_20(self):
        cohort = peers(21)
        cohort[-1] = deepcopy(cohort[0])
        result = compute_s11(target(), cohort, AT)
        self.assertIsNone(result["score"])
        self.assertIn("DUPLICATE_OR_TARGET_INCLUDED_IN_PEERS", result["missing"])
        cohort = peers(20) + [target()]
        result = compute_s11(target(), cohort, AT)
        self.assertIsNone(result["score"])
        self.assertIn("DUPLICATE_OR_TARGET_INCLUDED_IN_PEERS", result["missing"])

    def test_rank_deficient_ols_remains_na(self):
        cohort = peers()
        # Make all three OLS X-columns exactly collinear by using uniform
        # previous assets, revenue changes, and PPE; keep facts otherwise valid.
        for issuer_row in cohort:
            for fact in issuer_row["facts"]:
                if fact["metric"] == "TOTAL_ASSETS":
                    fact["value"] = 100
                if fact["metric"] == "PPE_NET":
                    fact["value"] = 30
                if fact["metric"] == "REVENUE" and fact["period_end"] == "2025-12-31":
                    old = next(x["value"] for x in issuer_row["facts"]
                               if x["metric"] == "REVENUE" and x["period_end"] == "2024-12-31")
                    fact["value"] = old + 10
        result = compute_s11(target(), cohort, AT)
        self.assertIsNone(result["score"])
        self.assertIn("INDUSTRY_YEAR_OLS_RANK_OR_FINITE_FAILURE", result["missing"])

    def test_negative_da_retains_sign_and_absolute_risk(self):
        sample = target()
        sample["facts"][0]["value"] -= 150  # cross source fallback's abs(DA) >= .20 floor
        result = compute_s11(sample, peers(), AT)
        self.assertEqual(result["score"], 0)
        self.assertEqual(result["components"]["discretionary_accrual_sign"], "INCOME_DECREASING")
        self.assertGreater(result["components"]["MJRisk_absolute_da"], .2)

    def test_evidence_hash_stable_under_peer_permutation_and_sensitive_to_source(self):
        cohort = peers()
        original = compute_s11(target(), cohort, AT)
        self.assertEqual(original["evidence_hash"],
                         compute_s11(target(), list(reversed(cohort)), AT)["evidence_hash"])
        amended = deepcopy(cohort)
        amended[0]["facts"][2]["evidence_hash"] = "cd" * 32
        changed = compute_s11(target(), amended, AT)
        self.assertNotEqual(original["evidence_hash"], changed["evidence_hash"])
        self.assertAlmostEqual(original["score"], changed["score"])

    def test_future_peer_facts_cannot_be_backfilled(self):
        cohort = peers()
        cohort[0]["facts"][1]["available_at"] = "2027-01-01T00:00:00Z"
        result = compute_s11(target(), cohort, AT)
        self.assertIsNone(result["score"])
        self.assertEqual(result["components"]["eligible_peer_count"], 19)

    def test_ambiguous_aliases_or_restatement_fail_closed(self):
        sample = target()
        duplicated = deepcopy(sample["facts"][-1])
        duplicated["metric"] = "ASSETS"
        sample["facts"].append(duplicated)
        result = compute_s11(sample, peers(), AT)
        self.assertIsNone(result["score"])
        self.assertIn("ASSETS_PREVIOUS_AMBIGUOUS_RESTATEMENT_OR_ALIAS", result["missing"])

    def test_no_naive_as_of(self):
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            compute_s11(target(), peers(), datetime(2026, 10, 11))


if __name__ == "__main__":
    unittest.main()
