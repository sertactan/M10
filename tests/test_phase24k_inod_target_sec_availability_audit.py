import hashlib
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from scripts.phase24k_inod_target_sec_availability_audit import audit

CIK="0000903651"


def fixture(base):
    db=base/"offline_backup.db"
    ids=[f"{CIK}-24-{i:06d}" for i in range(1,5)]
    with sqlite3.connect(db) as con:
        con.execute("CREATE TABLE security_master (security_id TEXT,cik TEXT)")
        con.execute("INSERT INTO security_master VALUES ('S1',?)",(CIK,))
        con.execute("""CREATE TABLE fundamental_facts_source
          (security_id TEXT, source TEXT,accession_number TEXT,available_at TEXT,
           accepted_at TEXT,filing_date TEXT,period_end TEXT,form_type TEXT)""")
        con.execute("CREATE INDEX idx_fundamental_accession ON fundamental_facts_source"
                    "(security_id,accession_number,source)")
        rows=[
            ("S1","SEC_EDGAR",ids[0],"2024-05-07T23:00:00Z",None,
             "2024-05-07","2024-03-31","10-Q"),
            ("S1","SEC_EDGAR",ids[1],"2024-05-08T21:00:00Z",None,
             "2024-05-09","2024-03-31","10-Q"),
            ("S1","SEC_EDGAR",ids[2],"2024-06-01T10:00:00Z",None,
             "2024-06-01","2024-03-31","10-K"),
        ]
        con.executemany("INSERT INTO fundamental_facts_source VALUES (?,?,?,?,?,?,?,?)",rows)
    sources=base/"sec_submissions"
    sources.mkdir()
    (sources/f"CIK{CIK}.json").write_text(json.dumps({
        "cik":int(CIK),
        "filings":{"recent":{
            "accessionNumber":ids,
            "filingDate":["2024-05-07","2024-05-09","2024-06-01","2022-01-01"],
            "form":["10-Q","10-Q","10-K","8-K"],
            "acceptanceDateTime":[
                "2024-05-07T22:00:00Z",
                "2024-05-08T21:30:00Z",
                "2024-06-01T09:00:00Z",
                "2022-01-01T15:00:00Z",
            ]},"files":[]},
    }))
    p_i=base/"phase24i.json"
    p_j=base/"phase24j.json"
    p_i.write_text(json.dumps({
        "schema":"MERIDYEN_PHASE24I_INOD_FINANCIAL_ACCESSION_YEAR_GAPS_V1",
        "status":"INOD_FINANCIAL_ACCESSION_DATE_GAPS_CLASSIFIED_REVIEW_ONLY",
        "PIT_approved":False,"database_modified":False,
        "window":{"start":"2024-01-01","end":"2025-09-30"},
        "total_valid_SEC_accessions":3,
        "accepted_UTC_before_filing_date_source_count":1,
        "filings_in_target_window_by_form":{"10-Q":1,"10-K":1},
        "financial_filings_no_fact_in_target_window_count":0,
    }))
    p_j.write_text(json.dumps({
        "schema":"MERIDYEN_PHASE24J_INOD_SEC_ACCEPTANCE_ET_CLASSIFICATION_V1",
        "status":"SEC_ACCEPTANCE_ET_CANDIDATES_REVIEW_ONLY_NO_DATE_REPAIR",
        "PIT_certified":False,"DB_modified":False,"timestamp_changed":False,
        "source_anomalies":1,
        "target_2024_2025_financial_anomalies":1,
        "target_2024_2025_financial_anomalies_with_existing_facts":1,
        "target_2024_2025_financial_anomalies_without_existing_facts":0,
    }))
    return db,sources,p_i,p_j


class TestPhase24k(unittest.TestCase):
    def test_target_accession_time_audit_never_approves_canonical(self):
        with TemporaryDirectory() as d:
            db,sources,p_i,p_j=fixture(Path(d))
            before=hashlib.sha256(db.read_bytes()).hexdigest()
            result=audit(db,sources,p_i,p_j)
            self.assertEqual(result["counts"]["accessions"],3)
            self.assertEqual(result["counts"]["quarantined_source_chronology_accessions"],1)
            self.assertEqual(result["accessions_by_review_class"][
                "SOURCE_AND_FACT_TIME_FIELDS_CONSISTENT_NOT_PIT"],2)
            self.assertEqual(result["accessions_with_issue_by_reason"][
                "LOOKAHEAD_RISK_AVAILABLE_BEFORE_SEC_ACCEPTANCE"],1)
            self.assertEqual(result["accessions_with_issue_by_reason"][
                "AFTER_HOURS_SEC_FILING_DATE_RULE_NOT_INDEPENDENTLY_VERIFIED"],1)
            self.assertFalse(result["eligible_for_canonical_PIT_promotion"])
            self.assertFalse(result["database_modified"])
            self.assertEqual(hashlib.sha256(db.read_bytes()).hexdigest(),before)

    def test_prior_tamper_must_fail(self):
        with TemporaryDirectory() as d:
            db,sources,p_i,p_j=fixture(Path(d))
            prior=json.loads(p_j.read_text())
            prior["target_2024_2025_financial_anomalies_with_existing_facts"]=99
            p_j.write_text(json.dumps(prior))
            with self.assertRaisesRegex(ValueError,
                                        "SOURCE_FACT_MATCH_COUNTS_CHANGED"):
                audit(db,sources,p_i,p_j)

    def test_missing_db_must_not_create(self):
        with TemporaryDirectory() as d:
            db,sources,p_i,p_j=fixture(Path(d))
            absent=Path(d)/"other.db"
            with self.assertRaisesRegex(ValueError,
                                        "OFFLINE_BACKUP_OR_SEC_SUBMISSIONS_MISSING"):
                audit(absent,sources,p_i,p_j)
            self.assertFalse(absent.exists())

    def test_bad_priors_fail_closed(self):
        with TemporaryDirectory() as d:
            db,sources,p_i,p_j=fixture(Path(d))
            prior=json.loads(p_i.read_text())
            prior["PIT_approved"]=True
            p_i.write_text(json.dumps(prior))
            with self.assertRaisesRegex(ValueError,"PRIOR_PIT_OR_DB_SAFETY_CLAIM_FAILED"):
                audit(db,sources,p_i,p_j)


if __name__=="__main__":
    unittest.main()
