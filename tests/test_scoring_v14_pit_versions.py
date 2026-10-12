"""Contract tests for version separation and fail-closed PIT diagnostics."""
from __future__ import annotations

from hashlib import sha256
import json
import unittest

from app.scoring_v14_pit_versions import ACCESSIONS, audit_versions


def _payloads() -> tuple[bytes, bytes, bytes, dict[str, bytes], dict[str, bytes]]:
    recent = {"accessionNumber": list(ACCESSIONS), "form": ["10-K", "10-K"],
              "reportDate": ["2024-12-31", "2025-12-31"],
              "acceptanceDateTime": ["2025-02-24T19:09:04Z", "2026-02-26T22:22:13Z"]}
    submissions = json.dumps({"cik": 903651, "filings": {"recent": recent}}).encode()
    receipt = json.dumps({"sha256": sha256(submissions).hexdigest(),
                          "bytes": len(submissions), "http_status": 200}).encode()
    concepts = {"CashAndCashEquivalentsAtCarryingValue": [46883000, 46897000],
                "AllowanceForDoubtfulAccountsReceivableCurrent": [1759000, 1256000]}
    facts = {"cik": 903651, "facts": {"us-gaap": {
        term: {"units": {"USD": [{"accn": ACCESSIONS[i], "end": "2024-12-31",
                                 "form": "10-K", "val": values[i]}
                                for i in (0, 1)]}}
        for term, values in concepts.items()}}}
    bodies, body_receipts = {}, {}
    for i, accession in enumerate(ACCESSIONS):
        year = (2024, 2025)[i]
        context = f"Duration_1_1_{year}_To_12_31_{year}"
        body = [f'<ix:nonNumeric name="dei:{field}" contextRef="{context}">{value}</ix:nonNumeric>'
                for field, value in (("EntityCentralIndexKey", "0000903651"),
                                     ("TradingSymbol", "INOD"),
                                     ("Security12bTitle", "Common Stock"),
                                     ("SecurityExchangeName", "NASDAQ"))]
        # The numeric tags sit inside a nonNumeric wrapper, like real iXBRL.
        body.append('<ix:nonNumeric name="test:Wrapper" contextRef="x">')
        for term, values in concepts.items():
            body.append(f'<ix:nonFraction name="us-gaap:{term}" scale="3" '
                        f'contextRef="As_Of_12_31_2024_x" unitRef="USD">'
                        f'{values[i] // 1000:,}</ix:nonFraction>')
        body.append('</ix:nonNumeric>')
        raw = "\n".join(body).encode()
        bodies[accession] = raw
        body_receipts[accession] = json.dumps({"sha256": sha256(raw).hexdigest(),
                                               "bytes": len(raw),
                                               "accession": accession,
                                               "form": "10-K",
                                               "source_authenticity_independently_verified": False}).encode()
    return submissions, receipt, json.dumps(facts).encode(), bodies, body_receipts


class PITVersionsTests(unittest.TestCase):
    def test_comparative_versions_and_administrative_asof(self) -> None:
        args = _payloads()
        before = audit_versions(*args, as_of="2025-03-01T00:00:00Z")
        after = audit_versions(*args, as_of="2026-03-01T00:00:00Z")
        self.assertEqual(before["administrative_acceptance_visible_accessions"], [ACCESSIONS[0]])
        self.assertEqual(after["administrative_acceptance_visible_accessions"], list(ACCESSIONS))
        self.assertEqual(before["changed_comparatives"]["CashAndCashEquivalentsAtCarryingValue"],
                         {"original_usd": 46883000, "later_comparative_usd": 46897000})
        self.assertEqual(before["canonical_asof_versions"], 0)
        self.assertEqual(before["s16c_normalized_pit_features"], 0)
        self.assertEqual(before["formal_restatement_status"], "UNDETERMINED")

    def test_modified_original_body_rejected(self) -> None:
        sub, receipt, facts, bodies, body_receipts = _payloads()
        bodies[ACCESSIONS[0]] += b"tampered"
        with self.assertRaisesRegex(ValueError, "PRIMARY_BODY_SEAL_MISMATCH"):
            audit_versions(sub, receipt, facts, bodies, body_receipts, as_of="2025-03-01T00:00:00Z")

    def test_companyfacts_conflict_rejected(self) -> None:
        sub, receipt, facts, bodies, body_receipts = _payloads()
        obj = json.loads(facts)
        obj["facts"]["us-gaap"]["CashAndCashEquivalentsAtCarryingValue"]["units"]["USD"][0]["val"] = 1
        with self.assertRaisesRegex(ValueError, "BODY_COMPANYFACTS_VERSION_CONFLICT"):
            audit_versions(sub, receipt, json.dumps(obj).encode(), bodies, body_receipts,
                           as_of="2025-03-01T00:00:00Z")

    def test_naive_asof_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "OFFSET_AWARE_TIMESTAMP_REQUIRED"):
            audit_versions(*_payloads(), as_of="2025-03-01T00:00:00")

    def test_submissions_receipt_http_failure_rejected(self) -> None:
        sub, receipt, facts, bodies, body_receipts = _payloads()
        bad = json.loads(receipt)
        bad["http_status"] = 429
        with self.assertRaisesRegex(ValueError, "SEC_SUBMISSIONS_SEAL_OR_ISSUER_INVALID"):
            audit_versions(sub, json.dumps(bad).encode(), facts, bodies, body_receipts,
                           as_of="2025-03-01T00:00:00Z")


if __name__ == "__main__":
    unittest.main()
