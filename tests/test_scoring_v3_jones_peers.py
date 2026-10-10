"""Synthetic SEC fixtures only; real INOD S11 remains N/A without dated peers."""
from __future__ import annotations

from copy import deepcopy
from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
import zipfile

from app.recovered_jones import compute_s11
from app.scoring_v3_jones_peers import (
    cached_archive_companyfacts, extract_company_year, read_universe, scan_available,
)
from tests.test_recovered_jones import issuer as synthetic_jones_issuer

AT = datetime(2026, 10, 11, tzinfo=timezone.utc)
CAPTURED = datetime(2026, 3, 5, tzinfo=timezone.utc)
ACCESSION = "0001104659-26-020655"
MAPPING = {
    "NET_INCOME": "NetIncomeLoss",
    "OPERATING_CASH_FLOW": "NetCashProvidedByUsedInOperatingActivities",
    "REVENUE": "RevenueFromContractWithCustomerExcludingAssessedTax",
    "ACCOUNTS_RECEIVABLE_NET": "AccountsReceivableNetCurrent",
    "PPE_NET": "PropertyPlantAndEquipmentNet",
    "TOTAL_ASSETS": "Assets",
}


def payloads(idx: int, *, actual_header=True):
    issuer = synthetic_jones_issuer(idx, target=(idx == 29))
    cik = issuer["cik"]
    concepts = {}
    for fact in issuer["facts"]:
        tag = MAPPING[fact["metric"]]
        concept = concepts.setdefault(tag, {"units": {"USD": []}})
        concept["units"]["USD"].append({
            "accn": ACCESSION, "form": "10-K",
            "val": fact["value"], "start": fact["period_start"],
            "end": fact["period_end"], "filed": "2026-03-01",
        })
        if fact["period_start"] is None:
            del concept["units"]["USD"][-1]["start"]
    companyfacts = json.dumps({
        "cik": int(cik), "entityName": f"SYNTHETIC {idx}",
        "facts": {"us-gaap": concepts},
    }, sort_keys=True).encode()
    submissions = json.dumps({
        "cik": int(cik), "sic": "7374", "name": f"SYNTHETIC {idx}",
        "filings": {"recent": {
            "accessionNumber": [ACCESSION], "form": ["10-K"],
            "reportDate": ["2025-12-31"], "filingDate": ["2026-03-01"],
            "acceptanceDateTime": ["2026-03-01T12:00:00Z"],
        }},
    }, sort_keys=True).encode()
    header = None
    if actual_header:
        header_bytes = (
            "<SEC-HEADER>\n"
            f"ACCESSION NUMBER: {ACCESSION}\n"
            "CONFORMED SUBMISSION TYPE: 10-K\n"
            "CONFORMED PERIOD OF REPORT: 20251231\n"
            f"CENTRAL INDEX KEY: {cik}\n"
            "STANDARD INDUSTRIAL CLASSIFICATION: SERVICES - SYNTHETIC [7374]\n"
            "</SEC-HEADER>\n"
        ).encode()
        header = {
            "header_bytes": header_bytes,
            "header_sha256": sha256(header_bytes).hexdigest(),
            "source_ref": (
                "https://www.sec.gov/Archives/edgar/data/"
                f"{int(cik)}/{ACCESSION.replace('-', '')}/{ACCESSION}.txt"
            ),
            "observed_at": "2026-03-05T00:00:00Z",
        }
    return issuer, companyfacts, submissions, header


def parse(idx, header=True):
    issuer, companyfacts, submissions, filing = payloads(idx)
    return extract_company_year(
        companyfacts, submissions, security_id=issuer["security_id"],
        ticker=f"FAKE{idx}", cik=issuer["cik"], as_of=AT,
        submissions_observed_at=CAPTURED, companyfacts_observed_at=CAPTURED,
        dated_industry=filing if header else None,
    )


class CompanyfactsJonesIngestTests(unittest.TestCase):
    def test_eight_exact_sec_fields_with_real_pinned_source_hashes(self):
        packet, receipt = parse(29)
        self.assertEqual(len(packet["facts"]), 8)
        self.assertEqual(len(receipt["selected"]), 8)
        self.assertFalse(receipt["missing"])
        self.assertTrue(receipt["historical_industry_provenance"][
            "original_header_content_sha_matches_local_bytes"])
        self.assertEqual(packet["industry"]["code"], "7374")
        self.assertEqual(packet["industry"]["effective_on"], "2025-12-31")
        self.assertTrue(all(f["accession"] == ACCESSION for f in packet["facts"]))
        self.assertTrue(all(f["source_ref"].endswith("CIK0001234029.json") for f in packet["facts"]))
        self.assertEqual(len({f["evidence_hash"] for f in packet["facts"]}), 8)

    def test_current_submissions_sic_cannot_substitute_dated_filing_header(self):
        result, receipt = parse(29, header=False)
        self.assertEqual(len(result["facts"]), 8)
        self.assertIsNone(result["industry"])
        self.assertEqual(receipt["reported_sec_sic_current_snapshot"], "7374")
        self.assertFalse(receipt["sic_snapshot_historical_fy_classification"])
        self.assertIn("DATED_SEC_INDUSTRY_CLASSIFICATION_FY2025", receipt["missing"])
        self.assertIsNone(compute_s11(result, [], AT)["score"])

    def test_fabricated_verified_flag_without_original_bytes_stays_na(self):
        iss, raw, submissions, header = payloads(29)
        entry = {"scheme": "SIC", "code": "7374", "cik": iss["cik"],
                 "historical_classification_verified": True,
                 "effective_on": "2025-12-31", "evidence_hash": "aa" * 32}
        obj, receipt = extract_company_year(
            raw, submissions, security_id=iss["security_id"], ticker="FAKE",
            cik=iss["cik"], as_of=AT, submissions_observed_at=CAPTURED,
            companyfacts_observed_at=CAPTURED, dated_industry=entry,
        )
        self.assertIsNone(obj["industry"])
        self.assertIn("DATED_SEC_INDUSTRY_CLASSIFICATION_FY2025", receipt["missing"])

    def test_tampered_header_sha_accession_cik_period_sic_and_url_fail_closed(self):
        for mutation in ("sha", "accession", "cik", "period", "sic", "url", "future"):
            with self.subTest(mutation=mutation):
                iss, raw, sub, header = payloads(29)
                if mutation in ("accession", "cik", "period", "sic"):
                    content = header["header_bytes"].decode()
                    old, new = {
                        "accession": (ACCESSION, "0001104659-26-020654"),
                        "cik": (iss["cik"], "0001234028"),
                        "period": ("20251231", "20241231"),
                        "sic": ("[7374]", "[737A]"),
                    }[mutation]
                    header["header_bytes"] = content.replace(old, new).encode()
                    header["header_sha256"] = sha256(header["header_bytes"]).hexdigest()
                elif mutation == "sha":
                    header["header_sha256"] = "bb" * 32
                elif mutation == "url":
                    header["source_ref"] = "https://fake.sec.invalid/test"
                else:
                    header["observed_at"] = "2027-01-01T00:00:00Z"
                packet, receipt = extract_company_year(
                    raw, sub, security_id=iss["security_id"], ticker="FAKE",
                    cik=iss["cik"], as_of=AT, submissions_observed_at=CAPTURED,
                    companyfacts_observed_at=CAPTURED, dated_industry=header,
                )
                self.assertIsNone(packet["industry"])
                self.assertIn("DATED_SEC_INDUSTRY_CLASSIFICATION_FY2025", receipt["missing"])

    def test_missing_tags_and_mismatched_accession_never_imputed(self):
        iss, raw, sub, header = payloads(29)
        obj = json.loads(raw)
        del obj["facts"]["us-gaap"]["PropertyPlantAndEquipmentNet"]
        packet, evidence = extract_company_year(
            json.dumps(obj).encode(), sub, security_id=iss["security_id"],
            ticker="FAKE", cik=iss["cik"], as_of=AT,
            submissions_observed_at=CAPTURED,
            companyfacts_observed_at=CAPTURED, dated_industry=header,
        )
        self.assertIsNone(packet)
        self.assertTrue(any("PPE_NET" in key for key in evidence["missing"]))
        obj = json.loads(raw)
        obj["facts"]["us-gaap"]["NetIncomeLoss"]["units"]["USD"][0]["accn"] = (
            "0001104659-26-020654"
        )
        packet, evidence = extract_company_year(
            json.dumps(obj).encode(), sub, security_id=iss["security_id"],
            ticker="FAKE", cik=iss["cik"], as_of=AT,
            submissions_observed_at=CAPTURED,
            companyfacts_observed_at=CAPTURED, dated_industry=header,
        )
        self.assertIsNone(packet)
        self.assertTrue(any("NET_INCOME" in key for key in evidence["missing"]))

    def test_fy2025_amended_10k_stops_old_filing_selection(self):
        iss, raw, sub, header = payloads(29)
        payload = json.loads(sub)
        for k, v in {
            "accessionNumber": "0001104659-26-090000",
            "form": "10-K/A",
            "reportDate": "2025-12-31",
            "filingDate": "2026-08-01",
            "acceptanceDateTime": "2026-08-01T12:00:00Z",
        }.items():
            payload["filings"]["recent"][k].append(v)
        packet, evidence = extract_company_year(
            raw, json.dumps(payload).encode(), security_id=iss["security_id"],
            ticker="FAKE", cik=iss["cik"], as_of=AT,
            submissions_observed_at=CAPTURED,
            companyfacts_observed_at=CAPTURED, dated_industry=header,
        )
        self.assertIsNone(packet)
        self.assertIn("FY2025_10K_AMENDMENT_REQUIRES_REVIEW", evidence["missing"])

    def test_fy2025_november_fiscal_end_exact_windows(self):
        iss, raw, sub, header = payloads(29)
        obj = json.loads(raw)
        for concept in obj["facts"]["us-gaap"].values():
            for row in concept["units"]["USD"]:
                if row["end"] == "2025-12-31":
                    row["end"] = "2025-11-30"
                    if "start" in row:
                        row["start"] = "2024-12-01"
                elif row["end"] == "2024-12-31":
                    row["end"] = "2024-11-30"
                    if "start" in row:
                        row["start"] = "2023-12-01"
        submission = json.loads(sub)
        submission["filings"]["recent"]["reportDate"][0] = "2025-11-30"
        header["header_bytes"] = header["header_bytes"].replace(b"20251231", b"20251130")
        header["header_sha256"] = sha256(header["header_bytes"]).hexdigest()
        packet, audit = extract_company_year(
            json.dumps(obj).encode(), json.dumps(submission).encode(),
            security_id=iss["security_id"], ticker="FAKE", cik=iss["cik"],
            as_of=AT, submissions_observed_at=CAPTURED,
            companyfacts_observed_at=CAPTURED, dated_industry=header,
        )
        self.assertFalse(audit["missing"])
        self.assertEqual(packet["period_start"], "2024-12-01")
        self.assertEqual(packet["period_end"], "2025-11-30")
        self.assertEqual(packet["facts"][3]["period_end"], "2024-11-30")

    def test_future_and_wrong_company_identity_fail_closed(self):
        iss, raw, sub, header = payloads(29)
        _, evidence = extract_company_year(
            raw, sub, security_id=iss["security_id"], ticker="FAKE", cik=iss["cik"],
            as_of=datetime(2026, 2, 28, tzinfo=timezone.utc),
            submissions_observed_at=CAPTURED,
            companyfacts_observed_at=CAPTURED, dated_industry=header,
        )
        self.assertIn("SOURCE_OBSERVED_AFTER_AS_OF", evidence["missing"])
        with self.assertRaises(ValueError):
            extract_company_year(
                raw, sub, security_id=iss["security_id"], ticker="FAKE",
                cik="BAD_CIK", as_of=AT, submissions_observed_at=CAPTURED,
                companyfacts_observed_at=CAPTURED, dated_industry=header,
            )
        wrong = json.loads(raw)
        wrong["cik"] = 1
        packet, evidence = extract_company_year(
            json.dumps(wrong).encode(), sub, security_id=iss["security_id"],
            ticker="FAKE", cik=iss["cik"], as_of=AT,
            submissions_observed_at=CAPTURED,
            companyfacts_observed_at=CAPTURED, dated_industry=header,
        )
        self.assertIsNone(packet)
        self.assertIn("SEC_CIK_MISMATCH", evidence["missing"])

    def test_20_synthetic_independent_peers_reach_the_original_jones_engine(self):
        candidate, evidence = parse(29)
        self.assertFalse(evidence["missing"])
        cohort = [parse(i)[0] for i in range(1, 21)]
        result = compute_s11(candidate, cohort, AT)
        self.assertIsNotNone(result["score"])
        self.assertEqual(result["components"]["eligible_peer_count"], 20)
        self.assertEqual(result["components"]["normalization"],
                         "ORIGINAL_ABSOLUTE_FALLBACK_100_MAX_0_1_MINUS_ABS_DA_OVER_0_20")
        self.assertFalse(result["canonical_accepted"])

    def test_exactly_nineteen_synthetic_peers_fail_closed(self):
        candidate, evidence = parse(29)
        result = compute_s11(candidate, [parse(i)[0] for i in range(1, 20)], AT)
        self.assertIsNone(result["score"])
        self.assertIn("ELIGIBLE_INDUSTRY_YEAR_PEERS_LT_20", result["missing"])

    def test_archive_cache_reads_only_named_cik_and_preserves_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            zpath = Path(folder) / "companyfacts.zip"
            _, raw, _, _ = payloads(29)
            with zipfile.ZipFile(zpath, "w") as z:
                z.writestr("CIK0001234029.json", raw)
            selected, evidence = cached_archive_companyfacts(zpath, "1234029")
            self.assertEqual(selected, raw)
            self.assertEqual(evidence["source_sha256"], sha256(raw).hexdigest())
            self.assertEqual(evidence["network_requests"], 0)
            selected, evidence = cached_archive_companyfacts(zpath, "1")
            self.assertIsNone(selected)
            self.assertEqual(evidence["status"], "CIK_NOT_IN_BULK_ZIP")

    def test_universe_readonly_immutable_does_not_write_to_source(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "operational.db"
            with closing(sqlite3.connect(path)) as connection:
                connection.executescript("""
                    CREATE TABLE security_master(
                      security_id TEXT,ticker TEXT,cik TEXT,active INTEGER);
                    CREATE TABLE security_classification_history(x TEXT);
                    INSERT INTO security_master VALUES ('FAKE','INOD','903651',1);
                """)
                connection.commit()
            before = sha256(path.read_bytes()).hexdigest()
            entries, audit = read_universe(path)
            self.assertEqual(audit["total_security_master"], 1)
            self.assertEqual(audit["classification_history_rows"], 0)
            self.assertEqual(entries[0]["cik"], "0000903651")
            self.assertEqual(before, sha256(path.read_bytes()).hexdigest())
            self.assertFalse((Path(str(path) + "-wal")).exists())

    def test_cache_only_scan_reports_zero_dated_peers_without_fake_sic(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "submissions").mkdir()
            _, raw, sub, header = payloads(29)
            with zipfile.ZipFile(root / "bulk.zip", "w") as z:
                z.writestr("CIK0001234029.json", raw)
            (root / "submissions" / "CIK0001234029.json").write_bytes(sub)
            target_identity = [{
                "security_id": "SYNTHETIC-29", "cik": "0001234029",
                "ticker": "INOD", "active": True,
            }]
            result = scan_available(
                target_identity, archive=root / "bulk.zip",
                submissions_directory=root / "submissions",
                as_of=AT, observed_at=CAPTURED,
            )
            self.assertIsNone(result["score"])
            self.assertEqual(len(result["target"]["selected"]), 8)
            self.assertEqual(result["candidate_peer_count"], 0)
            self.assertIn("DATED_INDUSTRY_CLASSIFICATION", result["blockers"])
            self.assertEqual(result["source"]["source_sha256"], sha256(raw).hexdigest())


if __name__ == "__main__":
    unittest.main()
