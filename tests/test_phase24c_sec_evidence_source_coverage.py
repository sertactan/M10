import hashlib
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from scripts.phase24c_sec_evidence_source_coverage import analyze


def _fixture(root: Path, *, include_fact_index: bool = True):
    db = root/"operational.db"
    con=sqlite3.connect(db)
    try:
        con.execute("CREATE TABLE security_master (security_id TEXT, cik TEXT)")
        con.execute("CREATE TABLE filing_records_source (security_id TEXT, source TEXT, filing_date TEXT, accepted_at TEXT, accession_number TEXT)")
        con.execute("CREATE TABLE ticker_aliases (security_id TEXT, alias TEXT, valid_from TEXT, valid_to TEXT, source TEXT, availability_date TEXT)")
        con.execute("CREATE TABLE fundamental_facts_source (security_id TEXT, source TEXT, filing_date TEXT, accepted_at TEXT, available_at TEXT, accession_number TEXT)")
        con.execute("CREATE INDEX idx_filing_records_pit ON filing_records_source(security_id,source)")
        con.execute("CREATE INDEX idx_alias_sid ON ticker_aliases(security_id)")
        if include_fact_index:
            con.execute("CREATE INDEX idx_fact_sid ON fundamental_facts_source(security_id)")
        con.executemany("INSERT INTO security_master VALUES (?,?)", [
            ("s1","0000000123"), ("s2","0000000456"), ("s3","0000000789")
        ])
        con.executemany("INSERT INTO fundamental_facts_source VALUES (?,?,?,?,?,?)",[
            ("s1","SEC_EDGAR","2024-05-01",None,"2024-05-02","acc01"),
            ("s2","SEC_EDGAR","2024-05-02",None,"2024-05-03","acc02"),
        ])
        con.executemany("INSERT INTO filing_records_source VALUES (?,?,?,?,?)",[
            ("s2","SEC_EDGAR","2024-05-02",None,"acc02"),
            ("s3","SEC_EDGAR","2024-05-03","2024-05-03T15:00:00+00:00","acc03"),
        ])
        con.execute("INSERT INTO ticker_aliases VALUES (?,?,?,?,?,?)",
                    ("s3","CCC","2024-01-01","2024-09-30","SEC_EDGAR","2024-01-01"))
        con.commit()
    finally:
        con.close()
    report=root/"phase24.json"
    records=[{
        "SimFinId":str(j+1), "local_security_id_candidates_NOT_verified":[sid]
    } for j,sid in enumerate(("s1","s2","s3"))]
    report.write_text(json.dumps({
        "schema":"MERIDYEN_PHASE24_SIMFIN_SEC_CIK_CANDIDATES_V1",
        "status":"SIMFIN_ID_TO_CIK_CANDIDATES_ONLY_ZERO_HISTORICAL_ID_CERTIFICATIONS",
        "reconciled_phase19_20_21_23":True,
        "historical_identity_certifications":0,
        "simfin_ids_in_window":3,
        "candidate_records":records,
    }))
    return db,report


class TestPhase24cSecSourceCoverage(unittest.TestCase):
    def test_validates_bounded_facts_vs_filing_coverage_without_writes(self):
        with TemporaryDirectory() as d:
            db,report=_fixture(Path(d))
            before=hashlib.sha256(db.read_bytes()).hexdigest()
            result=analyze(db,report,sample_ids=3)
            self.assertEqual(hashlib.sha256(db.read_bytes()).hexdigest(),before)
            self.assertEqual(result["sampled_candidate_security_ids"],3)
            self.assertEqual(result["candidate_security_ids_in_phase24"],3)
            self.assertTrue(result["global_bounded_sample"]["filing_table_any_rows"])
            self.assertTrue(result["global_bounded_sample"]["alias_table_any_rows"])
            self.assertEqual(result["bounded_sample_diagnosis"],{
                "SEC_FACTS_PRESENT_NO_FILING_RECORD_IN_BOUNDED_SAMPLE":1,
                "FILINGS_PRESENT_BUT_ACCEPTANCE_TIMESTAMP_MISSING_IN_SAMPLE":1,
                "SOME_SEC_ACCEPTANCE_EVIDENCE_PRESENT_IN_SAMPLE":1,
            })
            self.assertTrue(result["security_id_leading_indices"]["fundamental_facts_source"])
            self.assertFalse(result["canonical_historical_identity_certified"])
            self.assertFalse(result["database_modified"])
            self.assertEqual(result["api_calls"],0)

    def test_unindexed_giant_fact_table_protected(self):
        with TemporaryDirectory() as d:
            db,report=_fixture(Path(d),include_fact_index=False)
            result=analyze(db,report,sample_ids=3)
            self.assertFalse(result["security_id_leading_indices"]["fundamental_facts_source"])
            self.assertTrue(all(x.get("facts_skipped_missing_leading_index") for x in result["source_samples"]))

    def test_no_database_creation_on_missing_path(self):
        with TemporaryDirectory() as d:
            db,report=_fixture(Path(d))
            absent=Path(d)/"unavailable.sqlite"
            with self.assertRaisesRegex(ValueError,"REQUIRED_EXISTING_SOURCE_MISSING"):
                analyze(absent,report)
            self.assertFalse(absent.exists())

    def test_fails_closed_on_unverified_phase24_source(self):
        with TemporaryDirectory() as d:
            db,report=_fixture(Path(d))
            prev=json.loads(report.read_text())
            prev["historical_identity_certifications"]=1
            report.write_text(json.dumps(prev))
            with self.assertRaisesRegex(ValueError,"PHASE24_UNTRUSTED_OR_INCOMPLETE"):
                analyze(db,report)


if __name__=="__main__":
    unittest.main()
