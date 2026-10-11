from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.scoring_v13_pit_reconcile import reconcile
from scripts.scoring_v13_pit_reconcile import seal_or_verify


def fixture():
    accessions = [f"0001410578-25-{i:06d}" for i in range(1, 8)]
    accepted = [f"2025-01-{i:02d}T19:00:00Z" for i in range(1, 8)]
    sec = {"cik": "0000903651", "filings": {"recent": {
        "accessionNumber": accessions,
        "form": ["10-Q"] * 7,
        "filingDate": [f"2025-01-{i:02d}" for i in range(1, 8)],
        "acceptanceDateTime": accepted,
    }}}
    raw = json.dumps(sec).encode()
    receipt = json.dumps({"sha256": sha256(raw).hexdigest(), "bytes": len(raw),
                          "http_status": 200, "cik": "0000903651",
                          "checked_at": "2026-10-10T17:11:52Z"}).encode()
    k = {"eligible_for_canonical_PIT_promotion": False, "accessions": [
        {"accession": accessions[i], "form": "10-Q", "filing_date": f"2025-01-{i+1:02d}",
         "accepted_utc": accepted[i], "PIT_certified": False} for i in range(7)]}
    m = {"canonical_PIT_certified": False, "records": [
        {"accession": accessions[i], "form": "10-Q",
         "SEC_official_filing_date_unmodified": f"2025-01-{i+1:02d}",
         "SEC_accepted_utc_unmodified": accepted[i],
         "daily_PIT_replay_use_permitted": False} for i in range(7)]}
    return raw, receipt, k, m


class SevenAccessionTests(unittest.TestCase):
    def test_exact_seven_clock_joins_still_not_pit(self):
        raw, receipt, k, m = fixture()
        result = reconcile(raw, receipt, json.dumps(k).encode(), json.dumps(m).encode())
        self.assertEqual(result["administrative_joins_verified"], 7)
        self.assertEqual(result["canonical_pit_versions"], 0)
        self.assertTrue(all(row["first_public_at"] is None for row in result["rows"]))

    def test_tampered_acceptance_or_receipt_rejected(self):
        raw, receipt, k, m = fixture()
        k["accessions"][0]["accepted_utc"] = "2025-01-01T18:59:59Z"
        with self.assertRaisesRegex(ValueError, "CLOCK_CONFLICT"):
            reconcile(raw, receipt, json.dumps(k).encode(), json.dumps(m).encode())
        k["accessions"][0]["accepted_utc"] = "2025-01-01T19:00:00Z"
        with self.assertRaisesRegex(ValueError, "RECEIPT_MISMATCH"):
            reconcile(raw + b"x", receipt, json.dumps(k).encode(), json.dumps(m).encode())

    def test_upstream_canonical_claim_rejected(self):
        raw, receipt, k, m = fixture()
        m["records"][0]["daily_PIT_replay_use_permitted"] = True
        with self.assertRaisesRegex(ValueError, "PIT_STATUS_CONFLICT"):
            reconcile(raw, receipt, json.dumps(k).encode(), json.dumps(m).encode())

    def test_report_seal_and_exact_replay(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            data = b'{"canonical_pit_versions":0}\n'
            digest = seal_or_verify(path, data, verify=False)
            self.assertEqual(seal_or_verify(path, data, verify=True), digest)
            with self.assertRaisesRegex(ValueError, "REPLAY_OR_SHA_MISMATCH"):
                seal_or_verify(path, data + b"x", verify=True)
