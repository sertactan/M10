"""Offline Task9 regressions. Synthetic HTML is NEVER real INOD evidence."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from unittest import TestCase, main
from unittest.mock import patch

from app.scoring_v3_sec_filing_evidence import _extract_text
from app.task9_forensic_review import BLOCKS, SPECS, _anchored, review_contexts
from scripts.task9_forensic_review import _output_path

ACC = "0001104659-26-020655"
UTC = "2026-10-11T00:00:00Z"


def fake_source(text=None):
    if text is None:
        text = (
            "This entirely SYNTHETIC issuer filing sample discusses note X. "
            "The accountant inspected the original evidence at the same time. "
            "For the fictional current quarter, 77% of trade receivables were "
            "due from two customers, and the issuer tracked credit allowances. "
            "An additional independent test was documented. "
        ) * 9
    raw = ("<html><body><h1>INOD FAKE TEST ONLY</h1><p>"
           + text + "</p></body></html>").encode()
    parsed = _extract_text(raw)
    source = {
        "accession": ACC, "form": "10-K", "filing_date": "2026-02-26",
        "period_end": "2025-12-31", "sec_report_date": "2025-12-31",
        "accepted_at": "2026-02-26T22:22:13Z",
        "retrieved_at": "2026-10-10T18:00:00Z",
        "source_ref": "https://www.sec.gov/Archives/edgar/data/903651/"
                      "000110465926020655/fake-test.htm",
        "source_content_sha256": sha256(raw).hexdigest(),
        "extracted_text_sha256": sha256(parsed.encode()).hexdigest(),
    }
    return source, raw


TEST_SPEC = (("REC", ACC, "Synthetic note X, NOT an SEC result",
              "77% of trade receivables were due from two customers",
              ("credit allowances", "current quarter"), "ADVERSE_EXPOSURE",
              "Synthetic concentration example only.", "No proven default."),)


class Task9ForensicTests(TestCase):
    def test_seven_empty_risk_cells_are_review_required(self):
        src = {ACC: fake_source()}
        result = review_contexts(src, as_of=UTC, specs=TEST_SPEC)
        self.assertEqual(set(result["blocks"]), set(BLOCKS))
        self.assertEqual(result["blocks"]["REC"]["source_verified_findings"], 1)
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        self.assertIsNone(result["S13"])
        self.assertIsNone(result["serious_flag_count"])
        self.assertIsNone(result["independent_serious_flags"])
        self.assertTrue(all(b["risk"] is None and not b["coverage_complete"]
                            for b in result["blocks"].values()))

    def test_verified_full_context_has_source_hash_section_and_period(self):
        meta, raw = fake_source()
        result = review_contexts({ACC: (meta,raw)}, as_of=UTC, specs=TEST_SPEC)
        finding = result["blocks"]["REC"]["findings"][0]
        self.assertEqual(finding["filing_body_sha256"], sha256(raw).hexdigest())
        self.assertEqual(finding["period_end"], "2025-12-31")
        self.assertEqual(finding["section_reference"], TEST_SPEC[0][2])
        self.assertEqual(finding["anchor"], TEST_SPEC[0][3])
        self.assertEqual(finding["kind"], "ADVERSE_EXPOSURE")
        self.assertIsNone(finding["numeric_risk"])
        self.assertIn("77% of trade receivables", finding["context_excerpt"])
        self.assertTrue(len(finding["context_sha256"])==64)

    def test_keyword_match_without_corrob_is_not_evidence(self):
        spec = deepcopy(TEST_SPEC[0])
        spec = tuple(spec[:4]) + (("unavailable incompatible secondary evidence",),) + tuple(spec[5:])
        outcome = review_contexts({ACC:fake_source()}, as_of=UTC, specs=(spec,))
        self.assertEqual(outcome["blocks"]["REC"]["source_verified_findings"],0)
        self.assertEqual(len(outcome["unresolved_anchors"]),1)
        self.assertIsNone(outcome["S13"])

    def test_fraud_word_only_does_not_manufacture_serious_flags(self):
        rawtext = ("A public company may discuss fraud detection without fraud"
                   " having actually occurred. ") * 20
        result = review_contexts({ACC:fake_source(rawtext)}, as_of=UTC, specs=())
        self.assertIsNone(result["serious_flag_count"])
        self.assertIsNone(result["independent_serious_flags"])
        self.assertFalse(result["independence_review_complete"])

    def test_tampered_filing_body_hash_fails_closed(self):
        meta,raw=fake_source()
        with self.assertRaisesRegex(ValueError,"HASH"):
            review_contexts({ACC:(meta,raw+b"fake-tamper")},as_of=UTC,specs=TEST_SPEC)

    def test_issuer_and_sec_accession_bound(self):
        meta,raw=fake_source()
        bad=deepcopy(meta)
        bad["source_ref"]="https://www.sec.gov/Archives/edgar/data/1234567/000110465926020655/fake.htm"
        with self.assertRaisesRegex(ValueError,"HASH_OR_ISSUER"):
            review_contexts({ACC:(bad,raw)},as_of=UTC,specs=TEST_SPEC)

    def test_future_retrieval_rejected(self):
        meta,raw=fake_source()
        meta["retrieved_at"]="2026-10-12T00:00:00Z"
        with self.assertRaisesRegex(ValueError,"CLOCK"):
            review_contexts({ACC:(meta,raw)},as_of=UTC,specs=TEST_SPEC)

    def test_time_without_offset_rejected(self):
        with self.assertRaisesRegex(ValueError,"OFFSET"):
            review_contexts({ACC:fake_source()},as_of="2026-10-11T00:00:00",specs=TEST_SPEC)

    def test_context_duplicate_still_does_not_promote_score(self):
        meta,raw=fake_source()
        findings=review_contexts({ACC:(meta,raw)},as_of=UTC,specs=TEST_SPEC)
        info=findings["blocks"]["REC"]["findings"][0]
        self.assertGreater(info["corroborated_occurrences_in_source"],1)
        self.assertEqual(info["selection_policy"],"FIRST_CORROBORATED_PASSAGE_RESEARCH_ONLY_NO_SCORE")
        self.assertIsNone(findings["S13"])

    def test_s13_contract_keys_and_evidence_present(self):
        meta,raw=fake_source()
        out=review_contexts({ACC:(meta,raw)},as_of=UTC,specs=TEST_SPEC)
        self.assertEqual(out["source_contract"]["sha256"],
                         "53dce841fd5ebdfeb00636f327493be1255ea8b60e6df4eadd921a7098813794")
        self.assertEqual(out["source_contract"]["risk_rubric"],[0,25,50,75,100])
        self.assertEqual(sum(out["source_contract"]["weights"].values()),1)
        self.assertIsNone(out["human_review_packet"]["reviewer"])
        self.assertIsNone(out["human_review_packet"]["signed_risk_decisions"])
        self.assertFalse(out["canonical_accepted"])

    def test_output_is_private_and_create_only(self):
        from pathlib import Path
        import os
        with self.assertRaisesRegex(ValueError,"PRIVATE_TASK9"):
            _output_path(Path(os.environ.get("TEMP","C:/Temp"))/"task9_fake.json")


if __name__=="__main__":
    main()
