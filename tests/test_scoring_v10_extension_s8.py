"""Source statement math, alternative FFO rejection, integrity and replay."""
from __future__ import annotations

from decimal import Decimal, localcontext
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.scoring_v10_extension_s8 import (
    SEC_FY2025_KUSD, PARENT, V10, audit_extension,
    conditional_altman_z_double_prime, ffo_equivalence_gaps,
    source_bridges, verify_extension_receipt,
)


class ExtensionS8Tests(unittest.TestCase):
    def test_three_original_sec_statements_reconcile(self):
        b = source_bridges()
        self.assertEqual(b["retained_earnings"], "51158000")
        self.assertEqual(b["consolidated_equity"], "107062000")
        self.assertEqual(b["noncontrolling_equity"], "-83000")
        self.assertEqual(b["operating_profit_before_net_interest"], "39873000")
        self.assertEqual(b["cashflow_pre_working_capital"], "55766000")
        self.assertEqual(b["CFO_NOT_OHLSON_FFO"], "46752000")

    def test_invalid_arithmetic_in_original_transcription_fails_closed(self):
        for key, added in [("operating_profit", 1), ("retained_earnings", 1),
                           ("noncontrolling_equity", 1), ("operating_cash_flow", -1)]:
            altered = dict(SEC_FY2025_KUSD)
            altered[key] += added
            with self.subTest(key=key), self.assertRaisesRegex(
                    ValueError, "FILED_10K_BRIDGE_MISMATCH"):
                source_bridges(altered)

    def test_conditional_z_two_equity_bases_independent_decimal_reference(self):
        candidate = conditional_altman_z_double_prime()
        with localcontext() as ctx:
            ctx.prec = 60
            d = lambda x: Decimal(str(x))
            a, tl = d(168593), d(61531)
            common = (d("6.56") * (d(135394) - d(50532))/a +
                      d("3.26") * d(51158)/a +
                      d("6.72") * d(39873)/a)
            all_equity = common + d("1.05") * d(107062)/tl
            parent = common + d("1.05") * d(107145)/tl
        self.assertLess(abs(Decimal(candidate[
            "Z_double_prime_if_X3_is_operating_profit_and_X4_all_equity"])
            -all_equity), Decimal("1e-50"))
        self.assertLess(abs(Decimal(candidate[
            "Z_double_prime_if_X3_is_operating_profit_and_X4_parent_equity"])
            -parent), Decimal("1e-50"))
        self.assertNotEqual(parent, all_equity)
        self.assertIsNone(candidate["accepted_Z_Q"])
        self.assertIsNone(candidate["verified_original_S8_EBIT_variable"])

    def test_ffo_variants_produce_different_results_and_no_model_score(self):
        f = ffo_equivalence_gaps()
        alts = {i["amount_usd"] for i in f["separate_non_interchangeable_definitions"].values()}
        self.assertEqual(alts, {"39070000", "48314000", "55766000", "46752000"})
        for key in ("frozen_FFO", "frozen_FUTL", "accepted_O_Q", "S8"):
            self.assertIsNone(f[key])

    @unittest.skipUnless(V10.is_file(), "sealed offline V10 private evidence absent")
    def test_full_pinned_sec_companyfacts_replay_and_no_false_promotion(self):
        result = audit_extension()
        self.assertEqual(result["source_accession"], "0001104659-26-020655")
        self.assertEqual(result["official_SEC_index_observed"]["SIC"], "7374")
        self.assertEqual(result["prior_research_sic"], "7374")
        self.assertIsNone(result["official_SEC_index_observed"]["original_index_body_sha256"])
        self.assertEqual(result["new_real_FULL_S8_scores"], 0)
        self.assertIsNone(result["original_S8"])
        self.assertFalse(result["canonical_acceptance"])
        self.assertIsNone(result["source_original_HTML_sha256"])
        self.assertEqual(len(result["crosschecked_companyfacts_rows"]), 8)
        self.assertTrue(all(row["source_record_sha256"] for row in
                            result["crosschecked_companyfacts_rows"].values()))

    @unittest.skipUnless(V10.is_file(), "sealed offline V10 private evidence absent")
    def test_prior_receipt_replay_preserves_previous_online_evidence_scope(self):
        historic = PARENT / "inod_fy2025_v10_extension_v1.json"
        if not historic.exists():
            self.skipTest("first version private receipt unavailable")
        verified = verify_extension_receipt(historic)
        self.assertIsNone(verified["historic_original_10K_header_SIC_verification"])
        self.assertNotIn("official_SEC_index_observed", verified)


if __name__ == "__main__":
    unittest.main()
