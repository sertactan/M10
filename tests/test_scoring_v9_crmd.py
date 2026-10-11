"""Original SEC-file V9 CRMD S9 re-performance and fail-closed source tests."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.scoring_v9_crmd import calculate, debt_proof, gross_cost_proof
from scripts import scoring_v9_crmd as cli
from app.scoring_v8_s9_audit import audit_company


class CRMDOriginalFilingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.companyfacts, cls.submissions, cls.body25, cls.body24 = cli.sources()
        cls.partial = audit_company("CRMD", cls.companyfacts, cls.submissions,
                                    filing_body=cls.body25)

    def test_actual_nine_binary_signals_and_independent_decimal(self):
        result = calculate(self.companyfacts, self.submissions, self.body25, self.body24)
        self.assertEqual(result["score_status"], "REAL_SCORE_ACCEPTED_RESEARCH")
        self.assertEqual(result["model"], "S9")
        self.assertEqual(result["score_decimal"][:15], "55.555555555555")
        self.assertEqual(result["signal_count"], 5)
        self.assertEqual(result["verified_signals"], 9)
        self.assertEqual(result["positive_signal_count"], 5)
        self.assertEqual(result["signals"], result["independent_reference"]["signals"])
        self.assertEqual(result["signals"]["F_DELTA_GROSS_MARGIN"], 0)
        self.assertEqual(result["signals"]["F_DELTA_LEVERAGE"], 0)
        self.assertFalse(result["canonical_accepted"])
        self.assertFalse(result["historical_pit_accepted"])

    def test_gross_profit_missing_13872k_and_156k_is_intangible_amortization(self):
        proof = gross_cost_proof(self.body25, self.body24, self.partial)
        self.assertEqual(proof["years"]["2025"]["custom_ix_intangible_amortization_USD"],
                         "13872000")
        self.assertEqual(proof["years"]["2024"]["custom_ix_intangible_amortization_USD"],
                         "156000")
        self.assertEqual(proof["years"]["2025"]["total_original_v7_cogs_USD"],
                         "35961000")
        self.assertEqual(proof["years"]["2024"]["total_original_v7_cogs_USD"],
                         "3190000")
        self.assertEqual(proof["prior_original_10k_USD"]["total_cogs"], "3190534")
        self.assertEqual(proof["years"]["2025"]["gross_profit_USD"], "275748000")

    def test_balances_scaled_debt_and_fy2024_sole_operating_lease(self):
        proof = debt_proof(self.body25, self.body24)
        self.assertEqual(proof["fy2025_frozen_long_term_debt_USD"], "144626000")
        self.assertEqual(proof["fy2024_frozen_long_term_debt_USD"], "0")
        self.assertTrue(proof["critical_sec_companyfacts_tag_anomaly"][
            "companyfacts_note_tag_value_is_1000x_too_small"])
        self.assertEqual(proof["fy2024_original_total_liabilities_USD"], "34188723")

    def test_gross_cost_ix_scale_zero_does_not_pass(self):
        altered = self.body25.replace(
            b'name="crmd:AmortizationOfIntangibles" scale="3"',
            b'name="crmd:AmortizationOfIntangibles" scale="0"', 1,
        )
        self.assertNotEqual(altered, self.body25)
        with self.assertRaisesRegex(ValueError, "IX_TAG_SCALE"):
            gross_cost_proof(altered, self.body24, self.partial)

    def test_debt_ix_note_bad_scale_not_accepted(self):
        altered = self.body25.replace(
            b'name="us-gaap:ConvertibleDebtNoncurrent" scale="0"',
            b'name="us-gaap:ConvertibleDebtNoncurrent" scale="3"', 1,
        )
        self.assertNotEqual(altered, self.body25)
        with self.assertRaisesRegex(ValueError, "IX_SCALE_ANOMALY"):
            debt_proof(altered, self.body24)

    def test_2024_debt_zero_needs_original_audited_balance_sheet(self):
        altered = self.body24.replace(b"34,188,723", b"34,188,722", 1)
        self.assertNotEqual(altered, self.body24)
        with self.assertRaisesRegex(ValueError, "FY2024_ORIGINAL_EXHAUSTIVE"):
            debt_proof(self.body25, altered)

    def test_fy2024_original_source_sha_must_match(self):
        altered = self.body24 + b" "
        with self.assertRaisesRegex(ValueError, "OFFICIAL_BODY_SHA256_CHANGED"):
            calculate(self.companyfacts, self.submissions, self.body25, altered)

    def test_fy2025_current_body_sha_must_match(self):
        altered = self.body25 + b" "
        with self.assertRaisesRegex(ValueError, "OFFICIAL_FILING_BODY_SOURCE"):
            calculate(self.companyfacts, self.submissions, altered, self.body24)

    def test_companyfacts_source_sha_must_match(self):
        altered = self.companyfacts + b" "
        with self.assertRaisesRegex(ValueError, "COMPANYFACTS_PINNED_SHA256_CHANGED"):
            calculate(altered, self.submissions, self.body25, self.body24)

    def test_submissions_source_sha_must_match(self):
        altered = self.submissions + b" "
        with self.assertRaisesRegex(ValueError, "SEC_SUBMISSIONS_PINNED_SHA256_CHANGED"):
            calculate(self.companyfacts, altered, self.body25, self.body24)

    def test_original_and_comparative_periods_are_distinct(self):
        result = calculate(self.companyfacts, self.submissions, self.body25, self.body24)
        self.assertEqual(result["current_filing"]["period_end"], "2025-12-31")
        self.assertEqual(result["prior_filing"]["period_end"], "2024-12-31")
        self.assertEqual(result["selected_annual_facts"]["assets_2023"]["accession"],
                         result["prior_filing"]["accession"])
        self.assertEqual(result["selected_annual_facts"]["assets_2024"]["accession"],
                         result["current_filing"]["accession"])

    def test_cli_detects_resealed_fake_report_on_offline_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory) / "report.json"
            with patch.object(cli, "REPORT", dest):
                with patch.object(cli, "sources", return_value=(
                        self.companyfacts, self.submissions, self.body25, self.body24)):
                    generated = cli.sealed_report(receipt=dest)
                    self.assertEqual(generated["score_status"], "REAL_SCORE_ACCEPTED_RESEARCH")
                    again = cli.sealed_report(receipt=dest, verify_only=True)
                    self.assertEqual(again["receipt_sha256"], generated["receipt_sha256"])
                    tampered = json.loads(dest.read_bytes())
                    tampered["score"] = 100.0
                    forged = (json.dumps(tampered, indent=2, sort_keys=True,
                                         ensure_ascii=False, allow_nan=False) + "\n").encode()
                    dest.write_bytes(forged)
                    Path(str(dest)+".sha256").write_text(sha256(forged).hexdigest()+"\n")
                    with self.assertRaisesRegex(ValueError, "OFFLINE_REPLAY_OR_SEAL_FAILED"):
                        cli.sealed_report(receipt=dest, verify_only=True)


if __name__ == "__main__":
    unittest.main()
