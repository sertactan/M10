"""Synthetic filing attestations; never evidence of actual issuer S13 scores."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import unittest

from app.forensic_evidence import BLOCK_WEIGHTS, RUBRIC, SOURCE_SHA256, compute_s13

AT = datetime(2026, 10, 11, 0, 0, tzinfo=timezone.utc)
SOURCE_REF = "https://www.sec.gov/Archives/edgar/data/1234567/000110465926020655/synthetic-test.htm"


def fixture():
    filing = {"filing_id": "FY25", "cik": "0001234567", "accession": "0001104659-26-020655",
              "form_type": "10-K", "period_end": "2025-12-31", "source": "SEC_EDGAR",
              "source_ref": SOURCE_REF, "content_sha256": "ab" * 32,
              "accepted_at": "2026-02-26T22:22:13Z", "retrieved_at": "2026-10-09T12:00:00+00:00"}
    reviews = [{"block": block, "risk": 0, "filing_ids": ["FY25"],
                "reviewer": "synthetic reviewer", "reviewed_at": "2026-10-10T09:00:00+00:00",
                "coverage_complete": True, "rationale": "No red flag found in tested sections of this fake filing"}
               for block in BLOCK_WEIGHTS]
    flag_review = {"coverage_complete": True, "independence_review_complete": True,
                   "filing_ids": ["FY25"], "reviewer": "synthetic reviewer",
                   "reviewed_at": "2026-10-10T09:00:00+00:00",
                   "rationale": "Reviewed all seven blocks for independent serious red flags"}
    return {"issuer": {"ticker": "TEST", "cik": "0001234567"},
            "filings": [filing], "reviews": reviews,
            "flag_review": flag_review, "serious_flags": []}


def serious(packet, n):
    for i in range(n):
        block = list(BLOCK_WEIGHTS)[i % len(BLOCK_WEIGHTS)]
        next(r for r in packet["reviews"] if r["block"] == block)["risk"] = 75
        packet["serious_flags"].append({
            "flag_id": f"F{i}", "block": block, "severity": "SERIOUS",
            "finding": f"Synthetic serious event {i}", "independence_key": f"issue-{i}",
            "independence_basis": f"Separate synthetic underlying issue {i}",
            "filing_ids": ["FY25"]})
    return packet


class ForensicEvidenceTests(unittest.TestCase):
    def test_pinned_seven_block_source_contract(self):
        self.assertEqual(SOURCE_SHA256, "53dce841fd5ebdfeb00636f327493be1255ea8b60e6df4eadd921a7098813794")
        self.assertEqual(BLOCK_WEIGHTS, {"AUD": .25, "RPT": .15, "REC": .20,
                                         "DIL": .15, "REV": .10, "ACQ": .10, "GOV": .05})
        self.assertEqual(sum(BLOCK_WEIGHTS.values()), 1)
        self.assertEqual(RUBRIC, (0, 25, 50, 75, 100))

    def test_missing_review_never_defaults_to_zero(self):
        empty = compute_s13(None, AT)
        self.assertIsNone(empty["score"])
        self.assertEqual(empty["scope"], "RESEARCH_ONLY_NOT_CANONICAL_PIT")
        self.assertEqual(set(BLOCK_WEIGHTS) - set(empty["missing"]), set())
        partial = fixture()
        partial["reviews"] = partial["reviews"][:-1]
        self.assertIsNone(compute_s13(partial, AT)["score"])
        self.assertIn("GOV", compute_s13(partial, AT)["missing"])

    def test_all_seven_explicitly_clean_and_zero_flags(self):
        output = compute_s13(fixture(), AT)
        self.assertEqual(output["score"], 100)
        self.assertEqual(output["status"], "VERIFIED_RESEARCH_FORMULA")
        self.assertEqual(output["components"]["independent_serious_flag_count"], 0)
        self.assertFalse(output["canonical_accepted"])
        self.assertFalse(output["evidence"]["source_content_hashes_verified"])
        self.assertEqual(output["evidence"]["contract_lines"], [1707, 1833])

    def test_exact_seven_weighted_risks(self):
        packet = fixture()
        for row, risk in zip(packet["reviews"], (100, 75, 50, 25, 0, 25, 50)):
            row["risk"] = risk
        expected_risk = 100 * .25 + 75 * .15 + 50 * .20 + 25 * .15 + 0 * .10 + 25 * .10 + 50 * .05
        out = compute_s13(packet, AT)
        self.assertEqual(out["components"]["weighted_base_risk"], expected_risk)
        self.assertAlmostEqual(out["score"], 100 - expected_risk)
        self.assertEqual(out["components"]["independent_serious_flag_penalty"], 0)

    def test_independence_penalty_thresholds_and_clip(self):
        for n, penalty in ((0, 0), (1, 0), (2, 0), (3, 5), (4, 10), (5, 15), (6, 15)):
            with self.subTest(n=n):
                packet = serious(fixture(), n)
                out = compute_s13(packet, AT)
                self.assertEqual(out["components"]["independent_serious_flag_count"], n)
                self.assertEqual(out["components"]["independent_serious_flag_penalty"], penalty)
                base = out["components"]["weighted_base_risk"]
                self.assertAlmostEqual(out["score"], 100 - min(100, base + penalty))
        clip_packet = serious(fixture(), 5)
        for r in clip_packet["reviews"]:
            r["risk"] = 100
        self.assertEqual(compute_s13(clip_packet, AT)["score"], 0)

    def test_duplicate_independence_keys_fail_closed(self):
        packet = serious(fixture(), 3)
        packet["serious_flags"][2]["independence_key"] = packet["serious_flags"][1]["independence_key"]
        out = compute_s13(packet, AT)
        self.assertIsNone(out["score"])
        self.assertIn("DUPLICATE_OR_NOT_INDEPENDENT_SERIOUS_FLAGS", out["missing"])

    def test_review_and_independent_flag_audit_are_both_required(self):
        for key, val in (("coverage_complete", False), ("independence_review_complete", False),
                         ("rationale", ""), ("reviewed_at", "2027-01-01T00:00:00Z")):
            with self.subTest(key=key):
                packet = fixture()
                packet["flag_review"][key] = val
                out = compute_s13(packet, AT)
                self.assertIsNone(out["score"])
                self.assertIn("INDEPENDENT_SERIOUS_FLAG_REVIEW", out["missing"])
        packet = fixture()
        del packet["serious_flags"]
        self.assertIn("EXPLICIT_SERIOUS_FLAGS_LIST", compute_s13(packet, AT)["missing"])

    def test_review_cannot_claim_unchecked_risk(self):
        for key, val in (("coverage_complete", False), ("risk", 33), ("risk", -1),
                         ("risk", 0.0), ("rationale", ""),
                         ("reviewed_at", "2027-02-01T00:00:00Z"),
                         ("filing_ids", ["UNKNOWN"])):
            with self.subTest(key=key, val=val):
                packet = fixture()
                packet["reviews"][0][key] = val
                self.assertIsNone(compute_s13(packet, AT)["score"])

    def test_filing_receipts_issuer_source_time_and_hash_fail_closed(self):
        for key, val in (("cik", "987654"),
                         ("source", "SEC_SUBMISSIONS_INDEX"),
                         ("source_ref", "https://example.com/fake"),
                         ("source_ref", "https://www.sec.gov/Archives/edgar/data/1234567/000110465926020654/synthetic-test.htm"),
                         ("content_sha256", "not-a-hash"),
                         ("accepted_at", "2026-12-01T00:00:00Z"),
                         ("retrieved_at", "2026-02-01T00:00:00Z"),
                         ("retrieved_at", "2026-10-20T00:00:00Z"),
                         ("form_type", "8-K"),
                         ("period_end", "2026-12-31"),
                         ("available_at", "2025-01-01T00:00:00Z")):
            with self.subTest(key=key, val=val):
                packet = fixture()
                packet["filings"][0][key] = val
                out = compute_s13(packet, AT)
                self.assertIsNone(out["score"])
                self.assertIn("INVALID_OR_DUPLICATE_SEC_FILING_EVIDENCE", out["missing"])

    def test_flag_audit_must_cover_filing_scope_of_all_seven_blocks(self):
        packet = fixture()
        second = deepcopy(packet["filings"][0])
        second.update(filing_id="Q26", accession="0001104659-26-092021",
                      form_type="10-Q", period_end="2026-06-30",
                      source_ref="https://www.sec.gov/Archives/edgar/data/1234567/000110465926092021/synthetic-q.htm",
                      accepted_at="2026-08-06T20:15:14Z")
        packet["filings"].append(second)
        packet["reviews"][0]["filing_ids"].append("Q26")
        out = compute_s13(packet, AT)
        self.assertIsNone(out["score"])
        self.assertIn("INDEPENDENT_SERIOUS_FLAG_REVIEW_INCOMPLETE_FILING_SCOPE", out["missing"])
        packet["flag_review"]["filing_ids"].append("Q26")
        self.assertEqual(compute_s13(packet, AT)["score"], 100)

    def test_serious_flag_requires_linked_reviewed_evidence_and_risk(self):
        packet = serious(fixture(), 1)
        packet["serious_flags"][0]["filing_ids"] = ["UNKNOWN"]
        self.assertIn("INVALID_SERIOUS_FLAG_EVIDENCE", compute_s13(packet, AT)["missing"])
        packet = serious(fixture(), 1)
        packet["reviews"][0]["risk"] = 0
        self.assertIn("INVALID_SERIOUS_FLAG_EVIDENCE", compute_s13(packet, AT)["missing"])
        packet = serious(fixture(), 1)
        packet["serious_flags"][0]["independence_basis"] = ""
        self.assertIn("INVALID_SERIOUS_FLAG_EVIDENCE", compute_s13(packet, AT)["missing"])

    def test_duplicate_reviews_filing_ids_and_flags_fail_closed(self):
        packet = fixture()
        packet["reviews"].append(deepcopy(packet["reviews"][0]))
        self.assertIn("INVALID_OR_DUPLICATE_BLOCK_REVIEW", compute_s13(packet, AT)["missing"])
        packet = fixture()
        packet["filings"].append(deepcopy(packet["filings"][0]))
        self.assertIn("INVALID_OR_DUPLICATE_SEC_FILING_EVIDENCE", compute_s13(packet, AT)["missing"])
        packet = serious(fixture(), 2)
        packet["serious_flags"][1]["flag_id"] = packet["serious_flags"][0]["flag_id"]
        self.assertIn("DUPLICATE_OR_NOT_INDEPENDENT_SERIOUS_FLAGS", compute_s13(packet, AT)["missing"])

    def test_audit_digest_is_order_independent_but_changes_with_evidence(self):
        packet = serious(fixture(), 5)
        baseline = compute_s13(packet, AT)
        reordered = deepcopy(packet)
        reordered["reviews"].reverse()
        reordered["serious_flags"].reverse()
        self.assertEqual(compute_s13(reordered, AT)["evidence_hash"], baseline["evidence_hash"])
        altered = deepcopy(packet)
        altered["filings"][0]["content_sha256"] = "cd" * 32
        self.assertNotEqual(compute_s13(altered, AT)["evidence_hash"], baseline["evidence_hash"])
        altered = deepcopy(packet)
        altered["reviews"][0]["rationale"] += " Reviewed additional test pages"
        self.assertNotEqual(compute_s13(altered, AT)["evidence_hash"], baseline["evidence_hash"])
        altered = deepcopy(packet)
        altered["issuer"]["ticker"] = "TEST-ALIAS"
        self.assertNotEqual(compute_s13(altered, AT)["evidence_hash"], baseline["evidence_hash"])

    def test_naive_asof_rejected(self):
        with self.assertRaisesRegex(ValueError, "Offset-aware"):
            compute_s13(fixture(), datetime(2026, 10, 11))


if __name__ == "__main__":
    unittest.main()
