from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.scoring_v12_pit_audit import audit_sec_submissions, audit_version, select_as_of_version
from scripts.scoring_v12_pit_replay import report_bytes, write_or_verify


BODY = b"original SEC filing bytes"
BASE = {
    "cik": "0000903651", "concept": "Revenue", "period_end_at": "2024-12-31T23:59:59Z",
    "accession": "0001410578-25-000194", "accepted_at": "2025-02-24T19:09:04Z",
    "first_public_at": "2025-02-24T19:10:00Z",
    "public_time_basis": "INDEPENDENT_SOURCE_CAPTURE",
    "first_provider_available_at": "2025-02-24T19:12:00Z",
    "provider_time_basis": "HISTORICAL_CAPTURE_LOG",
    "captured_at": "2025-02-24T19:13:00Z",
    "capture_time_basis": "CONTEMPORANEOUS_ARCHIVE",
    "issuer_mapping_source": "historical exchange identity capture",
    "issuer_mapping_valid_at_as_of": True,
    "revision_kind": "ORIGINAL", "source_sha256": sha256(BODY).hexdigest(),
}


class PitAuditTests(unittest.TestCase):
 def test_full_clock_chain_and_provider_lookahead(self):
    assert audit_version(BASE, as_of="2025-02-24T19:13:00Z", source_bytes=BODY)["eligible"]
    early = audit_version(BASE, as_of="2025-02-24T19:11:00Z", source_bytes=BODY)
    assert not early["eligible"]
    assert "PROVIDER_ARRIVAL_AFTER_AS_OF" in early["reasons"]


 def test_acceptance_and_hash_alone_never_prove_historical_availability(self):
    row = {**BASE, "first_public_at": None, "first_provider_available_at": None,
           "captured_at": "2026-10-10T17:11:52Z"}
    result = audit_version(row, as_of="2026-10-11T00:00:00Z", source_bytes=BODY)
    assert not result["eligible"]
    assert "FIRST_PUBLICATION_UNVERIFIED" in result["reasons"]
    assert "HISTORICAL_PROVIDER_ARRIVAL_UNVERIFIED" in result["reasons"]


 def test_revisions_do_not_replace_original_before_publication(self):
    amended = {**BASE, "accession": "0001410578-25-000195", "revision_kind": "AMENDMENT",
               "amends_accession": BASE["accession"],
               "accepted_at": "2025-03-01T19:09:04Z", "first_public_at": "2025-03-01T19:10:00Z",
               "first_provider_available_at": "2025-03-01T19:12:00Z",
               "captured_at": "2025-03-01T19:13:00Z"}
    blobs = {BASE["accession"]: BODY, amended["accession"]: BODY}
    assert select_as_of_version([BASE, amended], as_of="2025-02-28T00:00:00Z", source_bytes=blobs)["selected_accession"] == BASE["accession"]
    assert select_as_of_version([BASE, amended], as_of="2025-03-02T00:00:00Z", source_bytes=blobs)["selected_accession"] == amended["accession"]


 def test_unsealed_body_and_forged_clock_order_block(self):
    row = {**BASE, "first_provider_available_at": "2025-02-24T19:08:00Z"}
    result = audit_version(row, as_of="2025-02-25T00:00:00Z", source_bytes=None)
    assert not result["eligible"]
    assert "PROVIDER_BEFORE_PUBLICATION" in result["reasons"]
    assert "SOURCE_BYTES_NOT_REPLAYED" in result["reasons"]


 def test_sealed_sec_submissions_is_administrative_only(self):
    raw = json.dumps({"cik": "0000903651", "filings": {"recent": {
        "accessionNumber": [BASE["accession"]],
        "acceptanceDateTime": [BASE["accepted_at"]], "form": ["10-K"],
        "filingDate": ["2025-02-24"], "reportDate": ["2024-12-31"],
    }}}).encode()
    receipt = {"sha256": sha256(raw).hexdigest(), "bytes": len(raw),
               "cik": "0000903651", "checked_at": "2026-10-10T17:11:52Z"}
    report = audit_sec_submissions(raw, receipt, [BASE["accession"]], as_of="2026-10-11T00:00:00Z")
    assert report["accepted_pit_versions"] == 0
    assert "HISTORICAL_PROVIDER_ARRIVAL_UNVERIFIED" in report["rows"][0]["reasons"]
    with self.assertRaisesRegex(ValueError, "HASH_OR_LENGTH"):
        audit_sec_submissions(raw + b"x", receipt, [BASE["accession"]], as_of="2026-10-11T00:00:00Z")

 def test_exact_private_replay_and_immutable_sidecar(self):
    with TemporaryDirectory() as directory:
        out = Path(directory) / "report.json"
        expected = report_bytes({"accepted_pit_versions": 0})
        digest = write_or_verify(out, expected, verify=False)
        self.assertEqual(out.with_name("report.json.sha256").read_text(encoding="ascii"), digest + "\n")
        self.assertEqual(write_or_verify(out, expected, verify=True), digest)
        with self.assertRaisesRegex(ValueError, "REPLAY_MISMATCH"):
            write_or_verify(out, report_bytes({"accepted_pit_versions": 1}), verify=True)
        out.with_name("report.json.sha256").write_text("0" * 64 + "\n", encoding="ascii")
        with self.assertRaisesRegex(ValueError, "SEAL_MISMATCH"):
            write_or_verify(out, expected, verify=True)

 def test_verify_seals_matching_legacy_crlf_without_replacing(self):
    with TemporaryDirectory() as directory:
        out = Path(directory) / "legacy.json"
        expected = report_bytes({"accepted_pit_versions": 0}, newline="\r\n")
        out.write_bytes(expected)
        self.assertEqual(write_or_verify(out, expected, verify=True), sha256(expected).hexdigest())
        self.assertEqual(out.read_bytes(), expected)
