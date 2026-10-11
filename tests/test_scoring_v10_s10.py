"""V10 frozen S10 regression and real SEC original-source regression tests.

All end-to-end tests use authentic locally cached SEC filing bodies and exact
Companyfacts members, never fabricated financial source/peer rows. Public CI
skips unavailable private caches while testing source-gating primitives.
"""
from __future__ import annotations

from decimal import Decimal
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from app.scoring_v10_s10 import (
    CRMD_10K, FROZEN_S10_SHA256, SOURCE_LOCATION,
    _original_fact, audit_original_archive, full_s10_gate,
    independent_four_beta_decimal, issuer_annual_inventory,
    prove_crmd_receivables, sic_from_original_10k_header,
    tca_dd_design, verified_cohort_regression,
)
from app.scoring_v8_s8_s10 import TARGETS
from app.scoring_v9_s8_s10 import verify_frozen_source
from scripts import scoring_v10_s10 as cli


class FrozenS10Gates(unittest.TestCase):
    def test_contract_source_sha_when_installed(self):
        if not SOURCE_LOCATION.is_file():
            self.skipTest("Original private plugin reference not bundled with GitHub CI")
        self.assertEqual(verify_frozen_source(), FROZEN_S10_SHA256)

    def test_no_peers_yields_no_regression(self):
        result = verified_cohort_regression({}, [], required_sic="7374", year=2024)
        self.assertEqual(result["eligible"], 0)
        self.assertIsNone(result["score"])
        self.assertEqual(result["minimum"], 20)

    def test_reused_jones_label_is_not_verified_s10_financial_source(self):
        reused = {"ticker":"FAKE", "cik":"0000000001",
                  "fiscal_year":2024, "historical_sic":"7374",
                  "accounting_regime":"US_GAAP",
                  "original_sec_verified":True,
                  "original_audit_regime_verified":True,
                  "membership_source_hash":"f"*64,
                  "original_10k_source_hash":"a"*64,
                  "dated_membership_verified":True}
        result = verified_cohort_regression({}, [reused],
                                            required_sic="7374",year=2024)
        self.assertEqual(result["eligible"],0)
        self.assertIsNone(result["beta"])

    def test_reject_invalid_original_sic_header(self):
        with self.assertRaisesRegex(ValueError,"ORIGINAL_EDGAR_HEADER"):
            sic_from_original_10k_header(b"SEC CURRENT SUBMISSIONS SIC 7374",
                cik="0000903651",accession="0001104659-26-020655",
                report_date="2025-12-31")

    def test_reject_unverified_ols_peer_count_without_fake_rows(self):
        with self.assertRaisesRegex(ValueError,"UNDER_20"):
            independent_four_beta_decimal([])

    def test_five_year_peer_and_frozen_tie_policy_never_fabricated(self):
        result=full_s10_gate([],[])
        self.assertEqual(result["status"],"S10_FIVE_VERIFIED_INDUSTRY_REGRESSIONS_MISSING")
        self.assertIsNone(result["score"])


class OriginalLocalSEC(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            if not SOURCE_LOCATION.is_file():
                raise FileNotFoundError("Private original frozen source is absent")
            if not cli.CACHE.is_dir():
                raise FileNotFoundError("Private original SEC archive cache absent")
            cls.body22=cli.cached_original(2022)
            cls.body23=cli.cached_original(2023)
            base=os.environ.get("LOCALAPPDATA")
            if not base:
                raise FileNotFoundError("Windows SEC archive absent")
            cls.zip_file=Path(base)/"S153ResearchTerminal/runtime/bulk/sec/companyfacts.zip"
            if not cls.zip_file.is_file():
                raise FileNotFoundError("Bulk SEC original ZIP absent")
        except (ValueError,OSError,FileNotFoundError) as error:
            raise unittest.SkipTest("Private Windows SEC source not mounted: "+str(error))
        with zipfile.ZipFile(cls.zip_file) as archive:
            cls.crmd_raw=archive.read("CIK0001410098.json")

    def test_original_sec_crmd_fy2022_ar_dash_zero(self):
        result=prove_crmd_receivables(self.body22,self.body23)
        self.assertEqual(result["2021"]["receivables_USD"],"45368")
        self.assertEqual(result["2022"]["receivables_USD"],"0")
        self.assertEqual(result["2022"]["proof"],
                         "FY2022_ORIGINAL_10K_BALANCE_SHEET_EXPLICIT_DASH")

    def test_2023_ar_absent_not_assigned_zero(self):
        result=prove_crmd_receivables(self.body22,self.body23)
        self.assertIsNone(result["2023"]["receivables_USD"])
        self.assertFalse(result["2023"]["numeric_AR_value_verified"])
        self.assertTrue(result["2023"]["total_current_assets_reconciles"])
        self.assertEqual(result["current_assets_FY2023_reconciliation_USD"],"79450400")

    def test_sec_fy2022_and_2023_original_filing_pins(self):
        self.assertEqual(sha256(self.body22).hexdigest(),CRMD_10K[2022]["sha256"])
        self.assertEqual(sha256(self.body23).hexdigest(),CRMD_10K[2023]["sha256"])
        self.assertEqual(CRMD_10K[2022]["accession"],"0001213900-23-024310")
        self.assertEqual(CRMD_10K[2023]["accession"],"0001213900-24-021585")

    def test_detect_tampered_historical_filing(self):
        with self.assertRaisesRegex(ValueError,"ORIGINAL_10K_SHA256_CHANGED"):
            prove_crmd_receivables(self.body22+b" ",self.body23)
        with self.assertRaisesRegex(ValueError,"ORIGINAL_10K_SHA256_CHANGED"):
            prove_crmd_receivables(self.body22,self.body23+b" ")

    def test_original_annual_accessions_and_actual_tca_rows(self):
        evidence=prove_crmd_receivables(self.body22,self.body23)
        inventory=issuer_annual_inventory("CRMD",self.crmd_raw,crmd_zero_evidence=evidence)
        self.assertEqual(inventory["annual"][2022]["accession"],
                         "0001213900-23-024310")
        self.assertEqual(inventory["annual"][2023]["accession"],
                         "0001213900-24-021585")
        year22=tca_dd_design(inventory,2022)
        year23=tca_dd_design(inventory,2023)
        self.assertEqual(year22["status"],"REAL_ORIGINAL_SEC_ANNUAL_TCA_DESIGN_DIAGNOSTIC")
        self.assertEqual(year23["status"],"REAL_ORIGINAL_SEC_ANNUAL_TCA_DESIGN_DIAGNOSTIC")
        self.assertEqual(year22["row"]["tca"],"2285613")
        self.assertEqual(year23["row"]["tca"],"14315240")
        self.assertFalse(year23["row"]["peer_eligible"])
        self.assertIn("original_accessions",year22["row"])

    def test_never_consider_fy2025_complete_without_audited_2026_cfo(self):
        evidence=prove_crmd_receivables(self.body22,self.body23)
        inventory=issuer_annual_inventory("CRMD",self.crmd_raw,crmd_zero_evidence=evidence)
        result=tca_dd_design(inventory,2025)
        self.assertIsNone(result["row"])
        self.assertIn("FY2026:ORIGINAL_10K_NOT_EVIDENCED",result["missing"])

    def test_reject_altered_companyfacts_member_hash(self):
        with self.assertRaisesRegex(ValueError,"PINNED_COMPANYFACTS_MISMATCH"):
            issuer_annual_inventory("CRMD",self.crmd_raw+b" ")

    def test_real_five_issuer_source_inventory_never_scores(self):
        result=audit_original_archive(self.zip_file,crmd_body22=self.body22,
                                      crmd_body23=self.body23)
        self.assertEqual(result["new_full_research_scores"],0)
        self.assertEqual(result["historical_canonical_PIT_accepted"],0)
        self.assertEqual(result["network_requests_for_replay"],0)
        self.assertEqual(set(result["stocks"]),set(TARGETS))
        for ticker, details in result["stocks"].items():
            self.assertIsNone(details["full_S10_score"])
            self.assertEqual(details["verified_five_year_sic_regime_panels"],0)
            self.assertIn("FY2026:ORIGINAL_10K_NOT_EVIDENCED",
                          details["years"]["2025"]["missing"])

    def test_real_offline_replay_rejects_forged_report_and_valid_new_seal(self):
        with tempfile.TemporaryDirectory() as path:
            private=Path(path)
            receipt=private/"report.json"
            with patch.object(cli,"PRIVATE",private):
                result=cli.store_or_verify(receipt=receipt)
                self.assertEqual(result["new_full_research_scores"],0)
                self.assertEqual(cli.store_or_verify(receipt=receipt,verify_only=True),
                                 result)
                tampered=json.loads(receipt.read_bytes())
                tampered["new_full_research_scores"]=1
                altered=(json.dumps(tampered,ensure_ascii=False,sort_keys=True,
                                    indent=2,allow_nan=False)+"\n").encode("utf8")
                receipt.write_bytes(altered)
                Path(str(receipt)+".sha256").write_text(
                    sha256(altered).hexdigest()+"\n")
                with self.assertRaisesRegex(ValueError,"OFFLINE_REPLAY_OR_SHA_SEAL_MISMATCH"):
                    cli.store_or_verify(receipt=receipt,verify_only=True)


if __name__ == "__main__":
    unittest.main()
