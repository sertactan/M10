"""Independently source-check ETON S6 diagnostic, never mislabel full score."""
import os
import json
from pathlib import Path
import unittest
import zipfile
from decimal import Decimal

from app.scoring_v10_extension_s6 import candidate_from_pinned_sec,CIK


class EtonOriginalSECS6(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p=Path(os.environ.get("LOCALAPPDATA",""))/"S153ResearchTerminal/runtime/bulk/sec/companyfacts.zip"
        if not p.is_file():
            raise unittest.SkipTest("Original pinned Windows SEC zip unavailable")
        with zipfile.ZipFile(p) as z:
            cls.raw=z.read("CIK"+CIK+".json")

    def test_three_original_annual_periods_and_component_values(self):
        got=candidate_from_pinned_sec(self.raw)
        y=got["years"]
        self.assertEqual(y["2023"]["A"]["value"],"31740000")
        self.assertEqual(y["2024"]["C"]["value"],"14936000")
        self.assertEqual(y["2025"]["INV"]["value"],"15419000")
        self.assertEqual(y["2025"]["ISSUE_CASH"]["value"],"598000")
        self.assertTrue(all(y[str(year)]["A"]["unit"]=="USD" for year in (2023,2024,2025)))

    def test_conditional_frozen_bin_not_full_score(self):
        got=candidate_from_pinned_sec(self.raw)
        f=Decimal(got["F_D_conditional"])
        self.assertTrue(Decimal("1")<f<Decimal("1.85"))
        self.assertEqual(got["candidate_bin"],"ORIGINAL_70_BIN_CANDIDATE_ONLY")
        self.assertIsNone(got["S6_score"])
        self.assertFalse(got["accepted_full_research"])
        self.assertIn("INDEPENDENT_WC_NCO_FIN_REVIEW_AND_ORIGINAL_PRIMARY_FILING_HASHES",got["missing"])

    def test_companyfacts_alteration_refused(self):
        with self.assertRaisesRegex(ValueError,"ETON_OFFICIAL_COMPANYFACTS_SHA_CHANGED"):
            candidate_from_pinned_sec(self.raw+b" ")


if __name__=="__main__": unittest.main()
