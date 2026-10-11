from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from app.scoring_v13_core_factors_sec import ACCESSION, calculate_raw_factors


class RawFactorTests(unittest.TestCase):
    def _sources(self, root: Path, *, capex_prior: int = 10) -> tuple[Path, Path]:
        values = {
            "RevenueFromContractWithCustomerExcludingAssessedTax": (200, 100, "USD"),
            "WeightedAverageNumberOfDilutedSharesOutstanding": (20, 10, "shares"),
            "NetCashProvidedByUsedInOperatingActivities": (50, 30, "USD"),
            "PaymentsToAcquirePropertyPlantAndEquipment": (10, capex_prior, "USD"),
        }
        facts = {}
        for tag, (current, prior, unit) in values.items():
            facts[tag] = {"units": {unit: [
                {"accn": ACCESSION, "start": "2025-01-01", "end": "2025-12-31",
                 "form": "10-K", "filed": "2026-02-26", "val": current},
                {"accn": ACCESSION, "start": "2024-01-01", "end": "2024-12-31",
                 "form": "10-K", "filed": "2026-02-26", "val": prior}]}}
        companyfacts = root / "companyfacts.json"
        companyfacts.write_text(json.dumps({"cik": 903651, "facts": {"us-gaap": facts}}))
        submissions = root / "submissions.json"
        submissions.write_text(json.dumps({"cik": "0000903651", "filings": {"recent": {
            "accessionNumber": [ACCESSION], "form": ["10-K"],
            "acceptanceDateTime": ["2026-02-26T22:22:13Z"]}}}))
        return companyfacts, submissions

    def _run(self, companyfacts: Path, submissions: Path) -> dict:
        pins = {"companyfacts": sha256(companyfacts.read_bytes()).hexdigest(),
                "submissions": sha256(submissions.read_bytes()).hexdigest()}
        with patch("app.scoring_v13_core_factors_sec.SOURCE_PINS", {"INOD": pins}), \
             patch("app.scoring_v13_core_factors_sec.verify_frozen_source", return_value="f"*64):
            return calculate_raw_factors(companyfacts, submissions)

    def test_exact_raw_formula_and_no_quality_score(self) -> None:
        with TemporaryDirectory() as tmp:
            companyfacts, submissions = self._sources(Path(tmp))
            result = self._run(companyfacts, submissions)
        self.assertEqual(result["calculations"]["F52_RPSGrowth_1Y"], "0")
        self.assertEqual(result["calculations"]["F53_FPSGrowth_1Y"], "0")
        self.assertIsNone(result["normalized_quality_scores"]["F52_RPS"])
        self.assertEqual(result["complete_s1_s2_s3_scores"], 0)

    def test_nonpositive_prior_fcf_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            companyfacts, submissions = self._sources(Path(tmp), capex_prior=30)
            with self.assertRaisesRegex(ValueError, "FCF-per-share growth undefined"):
                self._run(companyfacts, submissions)

    def test_pinned_source_tamper_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            companyfacts, submissions = self._sources(Path(tmp))
            original = sha256(companyfacts.read_bytes()).hexdigest()
            companyfacts.write_bytes(companyfacts.read_bytes() + b" ")
            with patch("app.scoring_v13_core_factors_sec.SOURCE_PINS", {"INOD": {
                    "companyfacts": original, "submissions": sha256(submissions.read_bytes()).hexdigest()}}):
                with self.assertRaisesRegex(ValueError, "SHA mismatch"):
                    calculate_raw_factors(companyfacts, submissions)


if __name__ == "__main__":
    unittest.main()
