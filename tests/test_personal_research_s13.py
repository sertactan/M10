"""Offline synthetic contract tests. No example represents a real SEC filing."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import unittest

from app.forensic_evidence import BLOCK_WEIGHTS, SOURCE_SHA256
from app.personal_research.s13_assessed import BLOCKS, VERSION, assess_s13
from app.scoring_v3_sec_filing_evidence import _extract_text
from app.task9_forensic_review import _anchored, review_contexts


ACC = "0001104659-26-020655"
SOURCE_URL = (
    "https://www.sec.gov/Archives/edgar/data/903651/"
    "000110465926020655/synthetic-test.htm")
STAMP = "2026-10-10T09:00:00Z"
AT = "2026-10-11T00:00:00Z"
SPEC = lambda b: (b, ACC, f"SYNTHETIC SEC test section {b}",
                  f"Fictional {b} risk passage", ("corroborated imaginary data",),
                  "SYNTHETIC_CONTEXT", f"Nonfactual {b} placeholder.",
                  "This is a synthetic unit test, not an issuer result.")


def packet():
    paragraphs = [
        "This is an imaginary company made solely for unit tests. " * 8,
        *[f"Fictional {b} risk passage with corroborated imaginary data. "
          "The narrative is invented, including every actor and number. "
          for b in BLOCKS],
        "An entirely fake annual filing to test hashes and offsets. " * 15,
    ]
    raw = ("<html><body><p>" + "</p><p>".join(paragraphs)
           + "</p></body></html>").encode("utf-8")
    parsed = _extract_text(raw)
    filing = {
        "cik": "0000903651", "accession": ACC, "form": "10-K",
        "source_ref": SOURCE_URL, "accepted_at": "2026-02-26T22:22:13Z",
        "retrieved_at": STAMP, "source_content_sha256": sha256(raw).hexdigest(),
        "extracted_text_sha256": sha256(parsed.encode()).hexdigest(),
        "body_bytes": raw,
    }
    meta = {
        "accession": ACC, "form": "10-K", "filing_date": "2026-02-26",
        "period_end": "2025-12-31", "sec_report_date": "2025-12-31",
        "source_ref": SOURCE_URL, "accepted_at": filing["accepted_at"],
        "retrieved_at": filing["retrieved_at"],
        "source_content_sha256": filing["source_content_sha256"],
        "extracted_text_sha256": filing["extracted_text_sha256"],
    }
    facts = [_anchored(SPEC(b), meta, parsed) for b in BLOCKS]
    assert all(facts), "Synthetic fixture must have genuine exact passage locators"
    ai = [
        {"block": b, "risk": 25, "coverage_complete": True,
         "assessment_type": "AI_PROPOSAL", "assessed_at": STAMP,
         "rationale": "Fictional manual AI risk opinion; no real source assertions.",
         "materiality_reason": "Invented materiality explanation for the unit test.",
         "alternative_explanation": "Could have a different fictitious interpretation.",
         "considered_finding_ids": [facts[i]["finding_id"]],
         "positive_finding_ids": [], "negative_finding_ids": [facts[i]["finding_id"]]}
        for i, b in enumerate(BLOCKS)]
    return {
        "ticker": "SYNTHETIC", "cik": "0000903651", "period_end": "2025-12-31",
        "as_of": AT, "filings": [filing], "source_findings": facts,
        "ai_reviews": ai, "serious_flags": [],
        "flag_review": {
            "assessment_type": "AI_PROPOSAL", "coverage_complete": True,
            "independence_review_complete": True, "assessed_at": STAMP,
            "reviewed_finding_ids": [f["finding_id"] for f in facts],
            "rationale": "All seven fictitious contexts screened explicitly."},
        "source_contract": {"sha256": SOURCE_SHA256,
                            "weights": dict(BLOCK_WEIGHTS),
                            "risk_rubric": [0, 25, 50, 75, 100]},
    }


def flag(p, block, suffix, *, independence_key=None, basis=None):
    source = next(f for f in p["source_findings"] if f["block"] == block)
    return {
        "assessment_type": "AI_PROPOSAL", "flag_id": f"FAKE-{suffix}",
        "block": block, "severity": "SERIOUS",
        "finding_ids": [source["finding_id"]],
        "finding": "Invented serious evidence, strictly a synthetic test.",
        "independence_key": independence_key or f"test-issue-{suffix}",
        "independence_basis": basis or "Separate hypothetical issue.",
    }


class PersonalS13Tests(unittest.TestCase):
    def test_no_packet_is_null_with_original_still_pending(self):
        result = assess_s13(None)
        self.assertIsNone(result["score"])
        self.assertEqual(result["status"], "UNRESOLVED")
        self.assertEqual(result["original_status"], "REVIEW_REQUIRED")
        self.assertFalse(result["canonical_accepted"])
        self.assertFalse(result["expert_approved"])
        self.assertEqual(set(result["blocks"]), set(BLOCKS))
        self.assertIsNone(result["receipt_sha256"])
        self.assertEqual(result["components"]["categories"]["AUD"]["observations"], 0)
        self.assertIsNone(result["components"]["flags"]["independent_count"])
        self.assertIn("MISSING_PERSONAL_S13_PACKET", result["missing"])

    def test_unidentified_request_has_no_receipt_but_complete_null_schema(self):
        for invalid in (
            {},
            {"ticker": "TEST", "cik": "0000903651", "as_of": "2026-10-12"},
            {"ticker": "TEST", "cik": "invalid", "as_of": AT},
        ):
            with self.subTest(invalid=invalid):
                out = assess_s13(invalid)
                self.assertIsNone(out["receipt_sha256"])
                self.assertIsNone(out["score"])
                self.assertEqual(out["original_status"], "REVIEW_REQUIRED")
                self.assertEqual(set(out["components"]["categories"]), set(BLOCKS))
                self.assertFalse(out["canonical_accepted"])

    def test_seven_verified_ai_opinions_produce_only_personal_score(self):
        out = assess_s13(packet())
        self.assertEqual(out["version"], VERSION)
        self.assertEqual(out["status"], "AI_ASSESSED_RESEARCH")
        self.assertEqual(out["score"], 75.0)
        self.assertEqual(out["numeric_result_type"], "SCENARIO")
        self.assertEqual(out["original_status"], "REVIEW_REQUIRED")
        self.assertTrue(out["provenance"]["source_content_hashes_verified"])
        self.assertEqual(out["provenance"]["verified_finding_count"], 7)
        self.assertEqual(out["components"]["categories"]["REC"]["verified_findings"], 1)
        self.assertEqual(out["blocks"]["AUD"]["negatives"][0]["accession"], ACC)
        self.assertEqual(out["blocks"]["AUD"]["negatives"][0]["source_ref"], SOURCE_URL)
        self.assertEqual(out["source_contract"]["sha256"], SOURCE_SHA256)
        self.assertFalse(out["canonical_accepted"])
        self.assertFalse(out["historical_pit_accepted"])
        self.assertEqual(len(out["receipt_sha256"]), 64)
        self.assertEqual(assess_s13(packet())["receipt_sha256"], out["receipt_sha256"])

    def test_weighted_risks_exact_original_contract(self):
        p = packet()
        risks = (100, 75, 50, 25, 0, 25, 50)
        for row, risk in zip(p["ai_reviews"], risks):
            row["risk"] = risk
        out = assess_s13(p)
        expected = sum(w * r for w, r in zip(BLOCK_WEIGHTS.values(), risks))
        self.assertAlmostEqual(out["components"]["weighted_base_risk"], expected)
        self.assertAlmostEqual(out["score"], 100 - expected)

    def test_partial_seven_source_observations_without_risk(self):
        p = packet()
        for i, f in enumerate(p["source_findings"]):
            # Legacy unsigned V5 form has source references but no exact offsets
            # and no body-passage excerpts, so it must remain a review packet.
            f.pop("anchor")
            f.pop("context_excerpt")
            f.pop("extracted_text_offset")
            f.pop("context_sha256")
        p["filings"] = []
        p["ai_reviews"] = []
        p["flag_review"] = {}
        out = assess_s13(p)
        self.assertEqual(out["status"], "REVIEW_REQUIRED")
        self.assertIsNone(out["score"])
        self.assertEqual({b: len(out["blocks"][b]["observations"]) for b in BLOCKS},
                         dict.fromkeys(BLOCKS, 1))
        self.assertTrue(all(out["blocks"][b]["observations"][0]["verification"]
                            == "RECEIPT_ONLY_UNVERIFIED" for b in BLOCKS))
        self.assertEqual(sum(out["components"]["categories"][b]["verified_findings"]
                             for b in BLOCKS), 0)
        self.assertIsNone(out["components"]["flags"]["independent_count"])
        self.assertEqual(len(out["receipt_sha256"]), 64)
        p["source_findings"][0]["observed_claim"] = "Another fictional observation"
        self.assertNotEqual(assess_s13(p)["receipt_sha256"], out["receipt_sha256"])

    def test_true_task9_review_packet_can_supply_source_findings(self):
        p = packet()
        metadata = {
            "accession": ACC, "form": "10-K", "filing_date": "2026-02-26",
            "period_end": "2025-12-31", "sec_report_date": "2025-12-31",
            "source_ref": SOURCE_URL, "accepted_at": p["filings"][0]["accepted_at"],
            "retrieved_at": p["filings"][0]["retrieved_at"],
            "source_content_sha256": p["filings"][0]["source_content_sha256"],
            "extracted_text_sha256": p["filings"][0]["extracted_text_sha256"],
        }
        # review_contexts requires the fixed INOD CIK in the fixture metadata,
        # but the SEC file and all contents are entirely fabricated for the test.
        source = review_contexts({ACC: (metadata, p["filings"][0]["body_bytes"])},
                                 as_of=AT, specs=tuple(SPEC(b) for b in BLOCKS))
        p.pop("source_findings")
        p["source_packet"] = source
        out = assess_s13(p)
        self.assertEqual(out["status"], "AI_ASSESSED_RESEARCH")
        self.assertEqual(out["provenance"]["verified_finding_count"], 7)

    def test_tampered_source_body_or_receipt_is_never_scored(self):
        for mutation in ("body", "sha", "url", "cik", "accepted", "retrieved"):
            with self.subTest(mutation=mutation):
                p = packet()
                f = p["filings"][0]
                if mutation == "body":
                    f["body_bytes"] += b"tampered"
                elif mutation == "sha":
                    f["source_content_sha256"] = "a" * 64
                elif mutation == "url":
                    f["source_ref"] = SOURCE_URL.replace("/903651/", "/11111/")
                elif mutation == "cik":
                    f["cik"] = "99999"
                elif mutation == "accepted":
                    f["accepted_at"] = "2026-10-13T00:00:00Z"
                else:
                    f["retrieved_at"] = "2027-01-01T00:00:00Z"
                out = assess_s13(p)
                self.assertIsNone(out["score"])
                self.assertFalse(out["provenance"]["source_content_hashes_verified"])
                self.assertIn("INVALID_FILING:0", out["missing"])

    def test_malformed_structured_values_fail_closed_not_raise(self):
        for path, malformed in (("form", ["10-K"]), ("accession", {}),
                                ("source_content_sha256", None)):
            with self.subTest(path=path):
                p = packet()
                p["filings"][0][path] = malformed
                self.assertIsNone(assess_s13(p)["score"])
        for path, malformed in (("accession", {}), ("filing_body_sha256", None),
                                ("context_sha256", [])):
            with self.subTest(path=path):
                p = packet()
                p["source_findings"][0][path] = malformed
                self.assertIsNone(assess_s13(p)["score"])

    def test_locator_excerpt_corroboration_and_hash_mutations_block(self):
        for key, val in (
            ("extracted_text_offset", 0), ("context_sha256", "f" * 64),
            ("filing_body_sha256", "e" * 64), ("anchor", "unsupported fact"),
            ("section_reference", ""), ("source_ref", "https://not-sec.example/a")):
            with self.subTest(key=key):
                p = packet()
                p["source_findings"][0][key] = val
                out = assess_s13(p)
                self.assertIsNone(out["score"])
                self.assertEqual(out["provenance"]["verified_finding_count"], 6)
                self.assertEqual(out["blocks"]["AUD"]["risk"], None)

    def test_rehashed_but_mislocated_excerpt_is_rejected(self):
        p = packet()
        f = p["source_findings"][0]
        f["context_excerpt"] = f["context_excerpt"].replace(
            "Fictional AUD risk passage", "Fictional REC risk passage")
        f["context_sha256"] = sha256(f["context_excerpt"].encode()).hexdigest()
        out = assess_s13(p)
        self.assertIsNone(out["score"])
        self.assertIn("UNLOCATED_OR_UNCORROBORATED_FINDING:0", out["missing"])

    def test_all_review_gates_fail_closed(self):
        changes = [
            lambda p: p["ai_reviews"].pop(),
            lambda p: p["ai_reviews"].append(deepcopy(p["ai_reviews"][0])),
            lambda p: p["ai_reviews"][0].update(risk=33),
            lambda p: p["ai_reviews"][0].update(risk=True),
            lambda p: p["ai_reviews"][0].update(risk=0.0),
            lambda p: p["ai_reviews"][0].update(coverage_complete=False),
            lambda p: p["ai_reviews"][0].update(considered_finding_ids=[]),
            lambda p: p["ai_reviews"][0].update(positive_finding_ids=["UNKNOWN"]),
            lambda p: p["ai_reviews"][0].update(assessed_at="2027-01-01T00:00:00Z"),
            lambda p: p["ai_reviews"][0].update(alternative_explanation=""),
            lambda p: p["ai_reviews"][0].update(assessment_type="EXPERT_SIGNED"),
            lambda p: p["flag_review"].update(independence_review_complete=False),
            lambda p: p.pop("serious_flags"),
            lambda p: p["flag_review"].update(reviewed_finding_ids=[]),
            lambda p: p.update(as_of="2026-10-11T00:00:00"),
            lambda p: p.update(period_end="2027-01-01"),
            lambda p: p["source_contract"].update(sha256="0" * 64),
        ]
        for i, change in enumerate(changes):
            with self.subTest(change=i):
                p = packet()
                change(p)
                self.assertIsNone(assess_s13(p)["score"])

    def test_penalty_count_and_clipping(self):
        for n, penalty in ((0, 0), (1, 0), (2, 0), (3, 5),
                           (4, 10), (5, 15), (6, 15)):
            with self.subTest(n=n):
                p = packet()
                p["serious_flags"] = [flag(p, BLOCKS[i], i) for i in range(n)]
                result = assess_s13(p)
                self.assertEqual(result["components"]["independent_serious_flag_count"], n)
                self.assertEqual(result["components"]["independent_serious_flag_penalty"], penalty)
                self.assertEqual(result["score"], 75 - penalty)
        p = packet()
        for review in p["ai_reviews"]:
            review["risk"] = 100
        p["serious_flags"] = [flag(p, BLOCKS[i], i) for i in range(5)]
        self.assertEqual(assess_s13(p)["score"], 0.0)

    def test_duplicate_cross_category_independence_key_counts_once(self):
        p = packet()
        p["serious_flags"] = [
            flag(p, "AUD", 0, independence_key="one-underlying-event"),
            flag(p, "REC", 1, independence_key="one-underlying-event")]
        out = assess_s13(p)
        self.assertEqual(out["score"], 75)
        self.assertEqual(out["components"]["independent_serious_flag_count"], 1)
        self.assertEqual(out["components"]["deduplicated_flag_mentions"], 1)
        self.assertEqual(set(out["flags"][0]["blocks"]), {"AUD", "REC"})
        self.assertEqual(len(out["flags"][0]["provenance"]), 2)

    def test_duplicate_finding_as_two_independent_events_fails_closed(self):
        p = packet()
        p["serious_flags"] = [flag(p, "AUD", 0), flag(p, "AUD", 1)]
        self.assertIsNone(assess_s13(p)["score"])
        self.assertIn("CONTRADICTORY_FLAG_INDEPENDENCE:1",
                      assess_s13(p)["missing"])

    def test_serious_flag_requires_positive_risk_and_attested_independence(self):
        p = packet()
        p["ai_reviews"][0]["risk"] = 0
        p["serious_flags"] = [flag(p, "AUD", 0)]
        self.assertIsNone(assess_s13(p)["score"])
        p = packet()
        p["serious_flags"] = [flag(p, "AUD", 0)]
        p["serious_flags"][0]["independence_basis"] = ""
        self.assertIsNone(assess_s13(p)["score"])
        self.assertIsNone(assess_s13(p)["components"]["flags"]["independent_count"])

    def test_unresolved_source_anchor_blocks_score(self):
        p = packet()
        p["source_packet"] = {
            "unresolved_anchors": [{"block": "RPT", "reason": "UNCHECKED_CONTEXT"}]}
        out = assess_s13(p)
        self.assertIsNone(out["score"])
        self.assertIn("SOURCE_PACKET_HAS_UNRESOLVED_ANCHORS", out["missing"])


if __name__ == "__main__":
    unittest.main()
