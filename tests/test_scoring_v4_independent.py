"""Adversarial clock/source controls; synthetic fixtures are not score evidence."""
import copy
from hashlib import sha256
import json
import unittest

from app.scoring_v4_independent import audit_source_clocks


class SourceClockTests(unittest.TestCase):
    def setUp(self):
        self.raw = json.dumps({"cik": "903651", "filings": {"recent": {
            "accessionNumber": ["0001104659-26-020655"],
            "acceptanceDateTime": ["2026-02-26T22:22:13Z"],
            "form": ["10-K"], "filingDate": ["2026-02-26"],
            "primaryDocument": ["inod-20251231x10k.htm"]}}}).encode()
        self.receipt = {"sha256": sha256(self.raw).hexdigest(), "bytes": len(self.raw),
                        "provider": "SEC_SUBMISSIONS", "http_status": 200,
                        "checked_at": "2026-10-10T17:11:52Z", "cik": "0000903651"}
        self.body = b"<html>synthetic body</html>"
        self.doc = {"schema": "M10_V3_PRIVATE_SEC_HTML_CACHE_RECEIPT_V1",
                    "accession": "0001104659-26-020655", "form": "10-K",
                    "source_ref": "https://www.sec.gov/Archives/edgar/data/903651/000110465926020655/inod-20251231x10k.htm",
                    "retrieved_at": "2026-10-10T18:22:05Z",
                    "bytes": len(self.body), "sha256": sha256(self.body).hexdigest()}

    def audit(self, as_of="2026-10-11T00:00:00Z"):
        return audit_source_clocks(self.raw, self.receipt, [(self.body, self.doc)], as_of=as_of)

    def test_current_research_is_not_historical_pit(self):
        result = self.audit()
        self.assertEqual(result["research_eligible_count"], 1)
        self.assertEqual(result["historical_pit_accepted_count"], 0)
        self.assertIsNone(result["rows"][0]["first_public_dissemination_at"])

    def test_acceptance_cannot_backdate_retrieval(self):
        result = self.audit("2026-03-01T00:00:00Z")
        self.assertEqual(result["research_eligible_count"], 0)
        self.assertIn("BODY_OBSERVED_AFTER_AS_OF", result["rows"][0]["reasons"])

    def test_both_sources_must_exist_by_asof(self):
        self.receipt["checked_at"] = "2026-10-12T00:00:00Z"
        self.assertIn("SUBMISSIONS_OBSERVED_AFTER_AS_OF", self.audit()["rows"][0]["reasons"])

    def test_wrong_primary_document_rejected_even_valid_hash(self):
        self.doc["source_ref"] = self.doc["source_ref"].replace("inod-20251231x10k", "exhibit99")
        self.assertIn("SEC_PRIMARY_DOCUMENT_URL_MISMATCH", self.audit()["rows"][0]["reasons"])

    def test_body_tamper_rejected(self):
        self.body += b"tamper"
        self.assertIn("BODY_RECEIPT_MISMATCH", self.audit()["rows"][0]["reasons"])

    def test_submissions_tamper_rejected(self):
        self.raw += b" "
        with self.assertRaisesRegex(ValueError, "SUBMISSIONS_RECEIPT_MISMATCH"):
            self.audit()

    def test_form_mismatch_rejected(self):
        self.doc["form"] = "8-K"
        self.assertIn("SEC_FORM_MISMATCH", self.audit()["rows"][0]["reasons"])

    def test_naive_clock_rejected(self):
        with self.assertRaisesRegex(ValueError, "OFFSET_AWARE_CLOCK_REQUIRED"):
            self.audit("2026-10-11T00:00:00")

    def test_duplicate_cannot_inflate_coverage(self):
        with self.assertRaisesRegex(ValueError, "DUPLICATE_DOCUMENT_RECEIPT"):
            audit_source_clocks(self.raw, self.receipt,
                                [(self.body, self.doc), (self.body, copy.deepcopy(self.doc))],
                                as_of="2026-10-11T00:00:00Z")

    def test_observation_before_acceptance_rejected(self):
        self.doc["retrieved_at"] = "2026-02-01T00:00:00Z"
        self.assertIn("SOURCE_OBSERVED_BEFORE_ACCEPTANCE", self.audit()["rows"][0]["reasons"])


if __name__ == "__main__":
    unittest.main()
