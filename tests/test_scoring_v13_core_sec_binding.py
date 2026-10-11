from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.scoring_v13_core_sec_binding import bind_sec_acceptance


class SourceBindingTests(unittest.TestCase):
    def _case(self, root: Path) -> tuple[Path, Path]:
        submissions = {"cik": "0000000001", "filings": {"recent": {
            "accessionNumber": ["0000000001-25-000001"],
            "acceptanceDateTime": ["2025-02-01T12:00:00Z"],
            "form": ["10-K"]}}}
        subs_path = root / "submissions.json"
        subs_path.write_text(json.dumps(submissions))
        source = "https://data.sec.gov/api/xbrl/companyfacts/CIK0000000001.json"
        evidence = {"accession": "0000000001-25-000001",
                    "available_at": "2025-02-02T00:00:00Z", "source_ref": source,
                    "period": "2024-12-31", "hash": "b"*64}
        row = {"value": 50, "unit": "0_100", "as_of": "2025-02-03T00:00:00Z",
               "available_at": "2025-02-02T00:00:00Z", "source_ref": source,
               "evidence_hash": "a"*64, "evidence": [evidence]}
        report = {"sec_submissions_sha256": sha256(subs_path.read_bytes()).hexdigest(),
                  "stocks": [{"ticker": "ONE", "features": {"D01_REVENUE_GROWTH_1Y_LEG": row}}]}
        report_path = root / "report.json"
        report_path.write_text(json.dumps(report))
        return report_path, subs_path

    def test_original_acceptance_bound_without_score_promotion(self) -> None:
        with TemporaryDirectory() as temp:
            report, subs = self._case(Path(temp))
            result = bind_sec_acceptance(report, subs, "ONE")
        self.assertEqual(result["partial_legs_bound"], 1)
        self.assertEqual(result["evidence_rows_bound"], 1)
        self.assertEqual(result["s1_s2_s3_complete_scores"], 0)
        self.assertFalse(result["canonical_pit_accepted"])

    def test_source_hash_tamper_rejected(self) -> None:
        with TemporaryDirectory() as temp:
            report, subs = self._case(Path(temp))
            subs.write_bytes(subs.read_bytes() + b" ")
            with self.assertRaisesRegex(ValueError, "SHA"):
                bind_sec_acceptance(report, subs, "ONE")

    def test_acceptance_after_availability_rejected(self) -> None:
        with TemporaryDirectory() as temp:
            report, subs = self._case(Path(temp))
            data = json.loads(report.read_text())
            row = data["stocks"][0]["features"]["D01_REVENUE_GROWTH_1Y_LEG"]
            row["evidence"][0]["available_at"] = "2025-01-31T00:00:00Z"
            report.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "timing/form"):
                bind_sec_acceptance(report, subs, "ONE")

    def test_issuer_source_mismatch_rejected(self) -> None:
        with TemporaryDirectory() as temp:
            report, subs = self._case(Path(temp))
            data = json.loads(report.read_text())
            data["stocks"][0]["features"]["D01_REVENUE_GROWTH_1Y_LEG"]["source_ref"] = "https://data.sec.gov/api/xbrl/companyfacts/CIK0000000002.json"
            report.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "CIK/source"):
                bind_sec_acceptance(report, subs, "ONE")


if __name__ == "__main__":
    unittest.main()
