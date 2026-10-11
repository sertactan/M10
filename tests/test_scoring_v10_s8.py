"""Strict accounting, source-seal, independent Decimal and offline replay gates."""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, localcontext
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.scoring_v10_s8 import (
    SCHEMA, V9_REPORT, TARGETS, audit_sources, check_seal,
    decimal_altman_parts, decimal_ohlson_non_ffo, sha_file,
    verify_private_receipt,
)


class V10S8Tests(unittest.TestCase):
    @unittest.skipUnless(V9_REPORT.is_file(),
        'Private original SEC/V9 receipt unavailable on public GitHub CI')
    def test_source_and_v9_seal_not_mutated(self):
        digest = check_seal(V9_REPORT)
        old = json.loads(V9_REPORT.read_text(encoding="utf8"))
        self.assertEqual(digest, old.get("source_v9_sha256", digest))
        self.assertEqual(old["frozen_source_sha256"],
                         "53dce841fd5ebdfeb00636f327493be1255ea8b60e6df4eadd921a7098813794")

    @unittest.skipUnless(V9_REPORT.is_file(),
        'Private original SEC/V9 receipt unavailable on public GitHub CI')
    def test_real_original_companyfacts_5_stock_full_evidence_replay(self):
        result = audit_sources()
        self.assertEqual(result["schema"], SCHEMA)
        self.assertEqual(result["network_requests"], 0)
        self.assertEqual(set(result["stocks"]), set(TARGETS))
        self.assertEqual(result["new_complete_S8_scores"], 0)
        for stock in result["stocks"].values():
            self.assertIsNone(stock["S8"])
            self.assertTrue(stock["V8_source_member_passed"])
            self.assertEqual(stock["FFO_and_FUTL"]["FFO"], None)
            self.assertFalse(stock["FFO_and_FUTL"]["reported_CFO_substitution_accepted"])
            self.assertTrue(stock["Ohlson_non_FFO_decimal"]["SIZE_decimal"])
            self.assertEqual(stock["v9_revised_GNP_and_SIZE"]["historical_as_of_vintage_verified"], False)
            self.assertIsNone(stock["Altman_decimal"]["Z"])

    @unittest.skipUnless(V9_REPORT.is_file(),
        'Private original SEC/V9 receipt unavailable on public GitHub CI')
    def test_altman_variant_and_market_equity_date(self):
        stock = audit_sources()["stocks"]
        self.assertEqual(stock["INOD"]["sic_and_Altman_variant"]["variant"],
                         "NONMANUFACTURING_Z_DOUBLE_PRIME")
        for ticker in ("TMDX", "CRMD", "PENG", "ETON"):
            self.assertEqual(stock[ticker]["sic_and_Altman_variant"]["variant"],
                             "PUBLIC_MANUFACTURING_Z")
            self.assertIn("EXACT_FY_END_DATED_MARKET_EQUITY",
                          stock[ticker]["Altman_decimal"]["missing"])
            self.assertFalse(stock[ticker]["SEC_cover_non_FY_end_public_float"]
                             ["eligible_as_FY_end_market_equity"])

    def test_original_ohlson_non_ffo_with_independent_decimal_reference(self):
        result = decimal_ohlson_non_ffo(168593000, 61531000, 120000000,
                                        25000000, 32181000, 27000000,
                                        "125.496", "18.246")
        with localcontext() as ctx:
            ctx.prec = 60
            a, l, ca, cl, ni, prior = map(Decimal,
                    [168593000, 61531000, 120000000, 25000000, 32181000, 27000000])
            size = (a / (Decimal(100)*Decimal("125.496")/Decimal("18.246"))).ln()
            reference = (Decimal("-1.32")-Decimal(".407")*size+
                        Decimal("6.03")*l/a-Decimal("1.43")*(ca-cl)/a+
                        Decimal(".0757")*cl/ca-Decimal("2.37")*ni/a-
                        Decimal(".521")*(ni-prior)/(ni+prior))
        self.assertLess(abs(Decimal(result["partial_logit_excluding_FUTL"])-reference),
                        Decimal("1e-50"))
        self.assertIsNone(result["O_Q"])

    def test_true_zero_vs_missing_and_chin_denominator(self):
        result = decimal_ohlson_non_ffo(1e6, 5e5, 4e5, 2e5, 0, 1,
                                        "125.496", "18.246")
        self.assertEqual(Decimal(result["weighted_terms"]["NITA"]), Decimal(0))
        with self.assertRaisesRegex(ValueError, "OHLSON_CHIN_ZERO_DENOMINATOR"):
            decimal_ohlson_non_ffo(1e6, 5e5, 4e5, 2e5, 0, 0,
                                   "125.496", "18.246")

    def test_independent_altman_weighted_terms_no_full_score(self):
        candidate = decimal_altman_parts(assets=1000, ca=400, cl=200,
              retained_earnings=100, liabilities=600, equity=400,
              revenue=700, variant="NONMANUFACTURING_Z_DOUBLE_PRIME")
        self.assertEqual(Decimal(candidate["weighted_terms"]["X1"]), Decimal("1.312"))
        self.assertIn("INDEPENDENT_EBIT_TO_TOTAL_ASSETS", candidate["missing"])
        self.assertIsNone(candidate["Z"])
        manufacturing = decimal_altman_parts(assets=1000, ca=400, cl=200,
              retained_earnings=100, liabilities=600, equity=None,
              revenue=700, variant="PUBLIC_MANUFACTURING_Z")
        self.assertEqual(manufacturing["factors"]["X5_REVENUE_A"], "0.7")
        self.assertIn("EXACT_FY_END_DATED_MARKET_EQUITY", manufacturing["missing"])

    @unittest.skipUnless(V9_REPORT.is_file(),
        'Private original SEC/V9 receipt unavailable on public GitHub CI')
    def test_no_market_value_from_public_float(self):
        stocks = audit_sources()["stocks"]
        for ticker, row in stocks.items():
            self.assertIsNone(row["fy_end_market_equity"], ticker)
            self.assertNotEqual(row["SEC_cover_non_FY_end_public_float"].get("date"),
                                row["fy_end"])

    @unittest.skipUnless(V9_REPORT.is_file(),
        'Private original SEC/V9 receipt unavailable on public GitHub CI')
    def test_full_offline_replay_and_reseal_tamper_rejection(self):
        source = audit_sources()
        with TemporaryDirectory() as folder:
            receipt = Path(folder) / "report.json"
            payload = (json.dumps(source, ensure_ascii=False, indent=2,
                                  sort_keys=True, allow_nan=False) + "\n").encode()
            receipt.write_bytes(payload)
            side = Path(str(receipt) + ".sha256")
            side.write_text(sha256(payload).hexdigest(), encoding="ascii")
            verified = verify_private_receipt(receipt)
            self.assertEqual(verified, source)
            forged = deepcopy(source)
            forged["stocks"]["INOD"]["S8"] = 99.0
            fake = json.dumps(forged, indent=2, sort_keys=True,
                              allow_nan=False, ensure_ascii=False).encode()
            receipt.write_bytes(fake)
            with self.assertRaisesRegex(ValueError, "SOURCE_SHA256_SEAL_CHANGED"):
                verify_private_receipt(receipt)
            side.write_text(sha256(fake).hexdigest(), encoding="ascii")
            with self.assertRaisesRegex(ValueError, "V10_SEC_DECIMAL_OFFLINE_REPLAY_MISMATCH"):
                verify_private_receipt(receipt)

    @unittest.skipUnless(V9_REPORT.is_file(),
        'Private original SEC/V9 receipt unavailable on public GitHub CI')
    def test_receipt_sidecar_v9_sha(self):
        self.assertEqual(check_seal(V9_REPORT), sha_file(V9_REPORT))


if __name__ == "__main__":
    unittest.main()
