"""Real-data checks and fail-closed source boundary for V10 extension peers."""
from __future__ import annotations

from pathlib import Path
import os
import unittest

from app.scoring_v10_extension_peers import (
    S11_TARGETS, s11_cohort_acceptance, verified_cached_historical_headers,
)
from app.scoring_v10_s10 import full_s10_gate, sic_from_original_10k_header


class ExtensionPeerTests(unittest.TestCase):
    def test_s10_empty_yearly_cohort_never_promotes(self):
        result=full_s10_gate([],[],accepted_percentile_rule=None)
        self.assertIsNone(result["score"])
        self.assertEqual(result["status"],"S10_FIVE_VERIFIED_INDUSTRY_REGRESSIONS_MISSING")

    def test_s11_under_20_rejected_even_with_exact_target(self):
        t=S11_TARGETS["TMDX"]
        prev={"ticker":"TMDX", "target_cik":t["cik"],
              "target":{"historical_sic":t["sic"],
                        "form_accession":"0001193125-26-067032",
                        "source_selected_count":8,"missing":[]},
              "required_peers":20,"verified_same_sic_independent_peers":0,
              "peer_observations":[], "s11_score":None,
              "status":"DATA_MISSING", "historical_pit_accepted":False,
              "canonical_accepted":False}
        checked=s11_cohort_acceptance(prev,ticker="TMDX")
        self.assertIsNone(checked["full_research_score"])
        self.assertEqual(checked["rejection_reasons"],[
            "S11_INDEPENDENT_ORIGINAL_SIC_PEERS_BELOW_20"])

    def test_empty_local_original_header_cache_not_historical_proof(self):
        data=verified_cached_historical_headers([])
        self.assertEqual(sum(len(x) for x in
                             data["verified_2020_2024_original_SIC_headers"].values()),0)
        self.assertEqual(data["historical_SIC_claims_from_current_directory"],0)

    def test_forged_sic_header_is_not_independently_evidenced(self):
        # Merely putting the correct SIC string in text is no original SGML.
        original=b"STANDARD INDUSTRIAL CLASSIFICATION: [3845]"
        with self.assertRaisesRegex(ValueError,"ORIGINAL_EDGAR_HEADER"):
            sic_from_original_10k_header(
                original,cik="0001756262",accession="0001193125-26-067032",
                report_date="2025-12-31")

    def test_s11_wrong_historical_sic_rejected_even_with_eight_target_fields(self):
        cfg=S11_TARGETS["PENG"]
        claim={"ticker":"PENG","target_cik":cfg["cik"],
               "target":{"historical_sic":"7374",
                         "form_accession":"0001616533-25-000061",
                         "source_selected_count":8,"missing":[]},
               "required_peers":20,"verified_same_sic_independent_peers":0,
               "peer_observations":[],"s11_score":None,
               "status":"DATA_MISSING","historical_pit_accepted":False,
               "canonical_accepted":False}
        checked=s11_cohort_acceptance(claim,ticker="PENG")
        self.assertIn("TARGET_ORIGINAL_10K_SIC_OR_EIGHT_FIELDS_UNPROVEN",
                      checked["rejection_reasons"])

    @unittest.skipUnless(Path("E:/M10/.scoring_v6_private/jones_tmdx/report.json").is_file(),
                         "Private original SEC cache is absent on this runner")
    def test_original_source_integration(self):
        from app.scoring_v10_extension_peers import offline_replay_s11
        runtime=Path(os.environ["LOCALAPPDATA"])/"S153ResearchTerminal"/"runtime"
        prior=Path("E:/M10/.scoring_v6_private")
        for ticker in ("TMDX","PENG"):
            with self.subTest(ticker=ticker):
                out=offline_replay_s11(ticker,legacy_root=prior,runtime=runtime)
                self.assertEqual(out["offline_SEC_requests"],0)
                self.assertTrue(out["offline_SEC_original_bytes_replayed"])
                self.assertLess(out["source_verified_independent_peers"],20)
                self.assertIsNone(out["full_research_score"])


if __name__ == "__main__":
    unittest.main()
