"""Synthetic SEC HTML fixtures; none represents a real INOD S13 risk finding."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from app.scoring_v3_sec_filing_evidence import (
    analyze_filing_body, assess_filing_collection, filing_manifest, reviewed_s13_only,
)
from scripts.scoring_v3_sec_filing_evidence import collect, _read_existing, FilingPolicyStop

NOW = "2026-10-11T04:00:00Z"
ACC = ("0001410578-25-000194", "0001104659-26-020655",
       "0001104659-26-057270", "0001104659-26-092021", "0001104659-26-092010")
FORM = ("10-K", "10-K", "10-Q", "10-Q", "8-K")
FILE = ("inod-20241231x10k.htm", "inod-20251231x10k.htm",
        "inod-20260331x10q.htm", "inod-20260630x10q.htm", "test-8k.htm")
DATES = ("2025-02-24", "2026-02-26", "2026-05-07", "2026-08-06", "2026-08-06")
PERIODS = ("2024-12-31", "2025-12-31", "2026-03-31", "2026-06-30", "")


def submissions():
    return json.dumps({"cik": 903651, "filings": {"recent": {
        "accessionNumber": list(ACC), "form": list(FORM), "primaryDocument": list(FILE),
        "filingDate": list(DATES), "reportDate": list(PERIODS),
        "acceptanceDateTime": [f"{day}T20:00:00Z" for day in DATES],
    }}}).encode()


def body():
    sections = (
        "INDEPENDENT REGISTERED PUBLIC ACCOUNTING FIRM audit opinion and internal control. "
        "Related party transactions disclosures. Accounts receivable and credit losses. "
        "Stock-based compensation and shares outstanding. "
        "Revenue recognition and remaining performance obligation. "
        "Goodwill and business combinations acquisition. Board of directors audit committee. "
        "There is no material weakness alleged in this SYNTHETIC fixture, but a term hit alone "
        "does not establish a risk or its absence. "
    )
    return ("<html><body><h1>FAKE SEC FILING - TEST ONLY</h1>" +
            "".join("<p>" + sections + "</p>" for _ in range(5)) +
            "<script>fraud must be ignored in HTML script</script></body></html>").encode()


class SecBodyTests(unittest.TestCase):
    def test_exact_manifest_annual_quarters_events_and_primary_source(self):
        items = filing_manifest(submissions())
        self.assertEqual(len(items), 5)
        self.assertEqual({r["period_end"] for r in items if r["form"] == "10-K"},
                         {"2024-12-31", "2025-12-31"})
        self.assertTrue(all(r["period_end"] is None
                            for r in items if r["form"].startswith("8-K")))
        self.assertTrue(all(r["source_ref"].startswith("https://www.sec.gov/Archives/edgar/data/903651/")
                            for r in items))
        with self.assertRaisesRegex(ValueError, "BUDGET"):
            filing_manifest(submissions(), max_8k=0)

    def test_mismatched_cik_array_and_directory_traversal_block(self):
        p = json.loads(submissions())
        p["cik"] = 123
        with self.assertRaisesRegex(ValueError, "ISSUER"):
            filing_manifest(json.dumps(p).encode())
        p = json.loads(submissions())
        p["filings"]["recent"]["form"].pop()
        with self.assertRaisesRegex(ValueError, "ARRAY"):
            filing_manifest(json.dumps(p).encode())
        p = json.loads(submissions())
        p["filings"]["recent"]["primaryDocument"][0] = "../evil.htm"
        with self.assertRaisesRegex(ValueError, "UNSAFE_PRIMARY"):
            filing_manifest(json.dumps(p).encode())

    def test_real_html_sections_have_hashes_but_no_risks(self):
        meta = filing_manifest(submissions())[0]
        out = analyze_filing_body(meta, body(), retrieved_at=NOW)
        self.assertEqual(out["source_content_sha256"], hashlib.sha256(body()).hexdigest())
        self.assertGreater(out["extracted_chars"], 1000)
        self.assertEqual(set(out["sections"]), {"AUD", "RPT", "REC", "DIL", "REV", "ACQ", "GOV"})
        self.assertTrue(all(out["sections"][k] for k in out["sections"]))
        self.assertTrue(out["unadjudicated_serious_term_hits"])
        self.assertIsNone(out["independent_serious_flags"])
        self.assertFalse(out["all_seven_blocks_reviewed"])
        self.assertFalse(out["risk_assigned"])
        self.assertFalse(out["historical_pit_accepted"])
        self.assertNotIn("fraud", {h["term"] for h in out["unadjudicated_serious_term_hits"]})

    def test_missing_body_and_candidate_hits_leave_s13_review_required(self):
        manifest = filing_manifest(submissions())
        evidence = [analyze_filing_body(manifest[0], body(), retrieved_at=NOW)]
        result = assess_filing_collection(manifest, evidence, as_of=NOW)
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        self.assertEqual(len(result["missing_body_accessions"]), 4)
        self.assertIsNone(result["serious_flag_count"])
        self.assertIsNone(result["S13"])
        for block in result["blocks"].values():
            self.assertIsNone(block["risk"])
            self.assertEqual(block["status"], "HUMAN_FILING_REVIEW_REQUIRED")

    def test_missing_human_review_never_creates_zero_risk(self):
        evidence = [analyze_filing_body(filing_manifest(submissions())[0], body(), retrieved_at=NOW)]
        result = reviewed_s13_only(None, evidence, as_of=NOW)
        self.assertIsNone(result["S13"])
        self.assertIn("INDEPENDENT_MANUAL_FILING_REVIEW", result["review_missing"])
        fake = {"filings": [{"accession": evidence[0]["accession"],
                            "source_ref": evidence[0]["source_ref"],
                            "content_sha256": "aa"*32}]}
        result = reviewed_s13_only(fake, evidence, as_of=NOW)
        self.assertIn("VERIFIED_SEC_FILING_BODY_HASH_AND_URL_BINDING", result["review_missing"])

    def test_private_cache_reuse_prevents_duplicate_network(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "submissions.json"
            source.write_bytes(submissions())
            cache = root / "bodies"
            calls = []
            def fake_download(row, agent):
                calls.append(row["accession"])
                return 200, body()
            with patch("scripts.scoring_v3_sec_filing_evidence._private_cache", return_value=cache), \
                 patch("scripts.scoring_v3_sec_filing_evidence._user_agent", return_value="TEST  reviewer@test.invalid"), \
                 patch("scripts.scoring_v3_sec_filing_evidence._fetch_body", side_effect=fake_download):
                first = collect(source, cache, contact=root / "config", offline=False,
                                max_downloads=5, as_of=NOW)
                self.assertEqual(first["body_filing_count"], 5)
                self.assertEqual(first["S13"], None)
                self.assertEqual(len(calls), 5)
                second = collect(source, cache, contact=None, offline=True,
                                 max_downloads=0, as_of=NOW)
                self.assertEqual(second["collection"]["network_requests_this_run"], 0)
                self.assertEqual(second["body_filing_count"], 5)
                self.assertEqual(len(calls), 5)
                cached = cache / filing_manifest(submissions())[0]["cache_name"]
                cached.write_bytes(body() + b"tampered")
                with self.assertRaisesRegex(FilingPolicyStop, "HASH"):
                    collect(source, cache, contact=None, offline=True,
                            max_downloads=0, as_of=NOW)

    def test_403_or_429_stops_all_other_requests_without_retries(self):
        for status in (403, 429):
            with self.subTest(status=status), TemporaryDirectory() as tmp:
                root = Path(tmp)
                src = root / "submissions.json"
                src.write_bytes(submissions())
                cache = root / "bodies"
                requested = []
                def deny(row, agent):
                    requested.append(row["accession"])
                    return status, None
                with patch("scripts.scoring_v3_sec_filing_evidence._private_cache", return_value=cache), \
                     patch("scripts.scoring_v3_sec_filing_evidence._user_agent", return_value="TEST contact@test.invalid"), \
                     patch("scripts.scoring_v3_sec_filing_evidence._fetch_body", side_effect=deny):
                    out = collect(src, cache, contact=src, offline=False,
                                  max_downloads=5, as_of=NOW)
                self.assertEqual(len(requested), 1)
                self.assertEqual(out["collection"]["network_requests_this_run"], 1)
                self.assertEqual(out["collection"]["download_failures"][0]["http_status"], status)
                self.assertEqual(out["body_filing_count"], 0)
                self.assertEqual(out["status"], "REVIEW_REQUIRED")


if __name__ == "__main__":
    unittest.main()
