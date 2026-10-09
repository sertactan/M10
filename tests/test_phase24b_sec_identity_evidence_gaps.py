from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from scripts.phase24b_sec_identity_evidence_gaps import analyze


def fixtures(root: Path):
    path = root / "operational.db"
    con = sqlite3.connect(path)
    try:
        con.execute(
            "CREATE TABLE security_master (security_id TEXT PRIMARY KEY,"
            "ticker TEXT, exchange TEXT, cik TEXT, share_class_figi TEXT,"
            "composite_figi TEXT)")
        con.executemany("INSERT INTO security_master VALUES (?,?,?,?,?,?)", [
            ("s1","AAA","NASDAQ","0000000123","BBG001",None),
            ("s2","BBB","NYSE","0000000456",None,None),
            ("s3","CCC","NASDAQ",None,None,None),
            ("s4","DDD","NASDAQ","0000000789",None,None),
        ])
        con.execute(
            "CREATE TABLE filing_records_source (security_id TEXT, source TEXT,"
            "cik TEXT, filing_date TEXT, accepted_at TEXT, accession_number TEXT)")
        con.executemany("INSERT INTO filing_records_source VALUES (?,?,?,?,?,?)", [
            ("s1","SEC_EDGAR","0000000123","2024-03-01","2024-03-01T12:20:00+00:00","abc"),
            ("s2","SEC_EDGAR","0000000456","2024-03-02",None,"def"),
            ("s4","SEC_EDGAR","0000000789","2024-04-10","2024-04-10T15:00:00Z","ghi"),
        ])
        con.execute(
            "CREATE TABLE ticker_aliases (security_id TEXT, alias TEXT,"
            "valid_from TEXT, valid_to TEXT, source TEXT, availability_date TEXT)")
        con.execute(
            "INSERT INTO ticker_aliases VALUES (?,?,?,?,?,?)",
            ("s1","AAA","2024-01-01","2024-06-30","SEC_EDGAR","2024-01-01"))
        con.commit()
    finally:
        con.close()
    items = []
    for sid, ticker, local, cik, classification in [
        ("100","AAA",["s1"],["0000000123"],"ONE_PRESENT_DAY_SEC_CIK_CANDIDATE_NOT_HISTORICAL_PROOF"),
        ("200","BBB",["s2"],["0000000456"],"ONE_PRESENT_DAY_SEC_CIK_CANDIDATE_NOT_HISTORICAL_PROOF"),
        ("300","CCC",["s3"],[],"NO_SEC_CIK_CANDIDATE"),
        ("400","DDD",["s4"],["0000000789"],"ONE_WEAK_PRESENT_DAY_CIK_CANDIDATE_REVIEW"),
        ("500","AAA",["s1","s2"],["0000000123","0000000456"],"MULTIPLE_CIK_OR_EXCHANGE_CANDIDATES_REVIEW"),
    ]:
        items.append({
            "SimFinId":sid,"ticker_strings":[ticker],
            "first_price_date":"2024-01-01","last_price_date":"2024-09-30",
            "local_security_id_candidates_NOT_verified":local,
            "candidate_CIKs_NOT_verified":cik,
            "review_class":classification,
        })
    report = root/"phase24.json"
    report.write_text(json.dumps({
        "schema":"MERIDYEN_PHASE24_SIMFIN_SEC_CIK_CANDIDATES_V1",
        "status":"SIMFIN_ID_TO_CIK_CANDIDATES_ONLY_ZERO_HISTORICAL_ID_CERTIFICATIONS",
        "reconciled_phase19_20_21_23":True,
        "historical_identity_certifications":0,
        "simfin_ids_in_window":len(items),
        "candidate_records":items,
    }))
    return report,path


class TestPhase24bSecIdentityEvidenceGaps(unittest.TestCase):
    def test_reads_prior_and_filing_alias_evidence_without_promotion(self):
        with TemporaryDirectory() as temp:
            report, db = fixtures(Path(temp))
            before = hashlib.sha256(db.read_bytes()).hexdigest()
            result = analyze(report, db)
            after = hashlib.sha256(db.read_bytes()).hexdigest()
            self.assertEqual(before,after)
            self.assertEqual(result["simfin_ids_reviewed"],5)
            self.assertEqual(result["review_classes"],{
                "SEC_ACCEPTANCE_AND_DATED_ALIAS_CANDIDATES_REVIEW":1,
                "CURRENT_MASTER_CIK_ONLY_NOT_HISTORICAL":1,
                "NO_SEC_CIK_CANDIDATE":1,
                "SEC_ACCEPTANCE_EVIDENCE_ONLY_REVIEW":1,
                "CONFLICT_OR_CHANGED_LOCAL_CIK_REQUIRES_REVIEW":1,
            })
            rows={x["SimFinId"]:x for x in result["records"]}
            self.assertEqual(rows["100"]["historical_sec_filing_with_timestamp_candidate_count"],1)
            self.assertEqual(rows["100"]["dated_ticker_alias_candidate_count"],1)
            self.assertEqual(rows["200"]["filing_without_timezone_or_missing_timestamp_count"],1)
            self.assertTrue(rows["100"]["current_share_class_figi_present_NOT_historic"])
            self.assertEqual(result["historic_SimFinId_CIK_certifications"],0)
            self.assertFalse(result["operational_database_modified"])
            self.assertFalse(result["model_training_performed"])

    def test_does_not_create_missing_database(self):
        with TemporaryDirectory() as temp:
            report, db = fixtures(Path(temp))
            missing=Path(temp)/"NO_DB.db"
            with self.assertRaisesRegex(ValueError,"OPERATIONAL_DB_MISSING"):
                analyze(report,missing)
            self.assertFalse(missing.exists())

    def test_rejects_untrusted_prior_canonical_claim(self):
        with TemporaryDirectory() as temp:
            report, db = fixtures(Path(temp))
            old = json.loads(report.read_text())
            old["historical_identity_certifications"]=5
            report.write_text(json.dumps(old))
            with self.assertRaisesRegex(ValueError,"PHASE24_REPORT_NOT_VERIFIED"):
                analyze(report,db)

    def test_rejects_duplicate_simfin_id(self):
        with TemporaryDirectory() as temp:
            report, db = fixtures(Path(temp))
            old=json.loads(report.read_text())
            old["candidate_records"][1]["SimFinId"]="100"
            report.write_text(json.dumps(old))
            with self.assertRaisesRegex(ValueError,"PHASE24_RECORD_COUNT_INVALID"):
                analyze(report,db)


if __name__=="__main__":
    unittest.main()
