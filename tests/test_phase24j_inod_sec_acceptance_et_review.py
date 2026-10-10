from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts.phase24j_inod_sec_acceptance_et_review import audit


CIK="0000903651"


def fixtures(base: Path):
    db=base/"backup.db"
    with closing(sqlite3.connect(db)) as con, con:
        con.execute("CREATE TABLE security_master (security_id TEXT, cik TEXT)")
        con.execute("INSERT INTO security_master VALUES (?,?)",("S1",CIK))
        con.execute("CREATE TABLE fundamental_facts_source "
                    "(security_id TEXT, accession_number TEXT, source TEXT)")
        con.execute("CREATE INDEX idx_fundamental_accession ON "
                    "fundamental_facts_source(security_id,accession_number,source)")
        con.execute("INSERT INTO fundamental_facts_source VALUES (?,?,?)",
                    ("S1",f"{CIK}-24-000001","SEC_EDGAR"))

    sec=base/"sec_submissions"
    sec.mkdir()
    ids=[f"{CIK}-24-{i:06d}" for i in range(1,5)]
    (sec/f"CIK{CIK}.json").write_text(json.dumps({
        "cik":int(CIK),
        "filings":{
            "recent":{
                "accessionNumber":ids,
                "form":["10-Q","10-K","8-K","10-Q"],
                "acceptanceDateTime":[
                    "2024-05-07T22:00:00Z",     # Tue 18 ET -> Wed filing
                    "2024-03-08T23:00:00Z",     # Fri 18 ET -> Mon filing
                    "2024-04-02T17:00:00Z",     # Tue 13 ET -> Wed filing: unresolved
                    "2024-05-01T20:00:00Z",
                ],
                "filingDate":[
                    "2024-05-08","2024-03-11",
                    "2024-04-03","2024-05-01",
                ],
            },
            "files":[],
        },
    }))

    old=base/"phase24h"
    old.mkdir()
    (old/"inod_sec_form_gap_review.json").write_text(json.dumps({
        "schema":"MERIDYEN_PHASE24H_INOD_SEC_FORM_GAP_REVIEW_V1",
        "status":"INOD_SEC_FORM_GAPS_CLASSIFIED_RESEARCH_ONLY_NOT_PIT",
        "pilot_CIK_not_historically_certified":CIK,
        "historical_PIT_certified":False,
        "database_modified":False,
        "source_before_filing_date_count_not_double_counted":3,
    }))
    newer=base/"phase24i"
    newer.mkdir()
    previous=newer/"inod_financial_accession_gaps.json"
    previous.write_text(json.dumps({
        "schema":"MERIDYEN_PHASE24I_INOD_FINANCIAL_ACCESSION_YEAR_GAPS_V1",
        "status":"INOD_FINANCIAL_ACCESSION_DATE_GAPS_CLASSIFIED_REVIEW_ONLY",
        "PIT_approved":False,
        "database_modified":False,
        "window":{"start":"2024-01-01","end":"2025-09-30"},
        "accepted_UTC_before_filing_date_source_count":3,
        "date_conflict_form_counts":{"10-K":1,"10-Q":1,"8-K":1},
    }))
    return db,sec,previous


class TestPhase24jSecDateClassification(unittest.TestCase):
    def test_afternoon_vs_after_hours_and_no_writes(self):
        with TemporaryDirectory() as temp:
            db,src,prior=fixtures(Path(temp))
            sha=hashlib.sha256(db.read_bytes()).hexdigest()
            result=audit(db,src,prior)
            self.assertEqual(result["source_anomalies"],3)
            self.assertEqual(result["by_class"],{
                "AFTER_1730_ET_NEXT_WEEKDAY_CANDIDATE_REVIEW":2,
                "NOT_EXPLAINED_BY_SIMPLE_AFTER_HOURS_RULE_REVIEW":1,
            })
            self.assertEqual(result["target_2024_2025_financial_anomalies"],2)
            self.assertEqual(result["target_2024_2025_financial_anomalies_with_existing_facts"],1)
            self.assertEqual(result["target_2024_2025_financial_anomalies_without_existing_facts"],1)
            self.assertFalse(result["timestamp_changed"])
            self.assertFalse(result["PIT_certified"])
            self.assertEqual(hashlib.sha256(db.read_bytes()).hexdigest(),sha)

    def test_absent_db_fails_without_create(self):
        with TemporaryDirectory() as temp:
            db,src,prior=fixtures(Path(temp))
            absent=Path(temp)/"absent.db"
            with self.assertRaisesRegex(ValueError,"OFFLINE_BACKUP_OR_PRIOR_REPORT_UNAVAILABLE"):
                audit(absent,src,prior)
            self.assertFalse(absent.exists())

    def test_source_report_count_mismatch_fails_closed(self):
        with TemporaryDirectory() as temp:
            db,src,prior=fixtures(Path(temp))
            r=json.loads(prior.read_text())
            r["accepted_UTC_before_filing_date_source_count"]=20
            prior.write_text(json.dumps(r))
            with self.assertRaisesRegex(ValueError,"SEC_SOURCE_ANOMALIES_CHANGED_OR_TRUNCATED"):
                audit(db,src,prior)

    def test_pit_approved_claim_rejected(self):
        with TemporaryDirectory() as temp:
            db,src,prior=fixtures(Path(temp))
            r=json.loads(prior.read_text())
            r["PIT_approved"]=True
            prior.write_text(json.dumps(r))
            with self.assertRaisesRegex(ValueError,"PHASE24I_REPORT_NOT_VERIFIED"):
                audit(db,src,prior)


if __name__=="__main__":
    unittest.main()
