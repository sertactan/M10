import hashlib
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from scripts.phase24i_inod_financial_accession_year_gaps import analyze

CIK = "0000903651"


def fixture(root: Path):
    db=root/"inod-backup.db"
    con=sqlite3.connect(db)
    con.execute("CREATE TABLE security_master (security_id TEXT, cik TEXT)")
    con.execute("INSERT INTO security_master VALUES (?,?)",("S1",CIK))
    con.execute("CREATE TABLE fundamental_facts_source (security_id TEXT, accession_number TEXT, source TEXT)")
    con.execute("CREATE INDEX idx_fundamental_accession ON fundamental_facts_source(security_id,accession_number,source)")
    ids=[f"{CIK}-24-{i:06d}" for i in range(1,8)]
    con.executemany("INSERT INTO fundamental_facts_source VALUES (?,?,?)",[
        ("S1",ids[0],"SEC_EDGAR"),
        ("S1",ids[1],"SEC_EDGAR"),
    ])
    con.commit()
    con.close()

    forms=["10-Q","10-K","10-Q","10-K/A","10-K","8-K","10-Q"]
    filing_dates=["2024-02-20","2025-03-05","2025-05-05",
                  "2025-03-05","2022-03-01","2025-04-01","2025-05-09"]
    accepted=["2024-02-20T20:00:00Z","2025-03-05T20:00:00Z",
              "2025-05-05T20:00:00Z","2025-03-05T20:00:00Z",
              "2022-03-01T20:00:00Z","2025-04-01T20:00:00Z",
              "2025-05-08T21:00:00Z"]
    sec=root/"sec"
    sec.mkdir()
    (sec/f"CIK{CIK}.json").write_text(json.dumps({
        "cik":int(CIK),
        "filings":{"recent":{
            "accessionNumber":ids,
            "form":forms,
            "filingDate":filing_dates,
            "acceptanceDateTime":accepted,
        },"files":[]},
    }))
    phase24h=root/"phase24h.json"
    phase24h.write_text(json.dumps({
        "schema":"MERIDYEN_PHASE24H_INOD_SEC_FORM_GAP_REVIEW_V1",
        "status":"INOD_SEC_FORM_GAPS_CLASSIFIED_RESEARCH_ONLY_NOT_PIT",
        "pilot_CIK_not_historically_certified":CIK,
        "historical_PIT_certified":False,
        "database_modified":False,
        "valid_accessions_total":6,
        "source_before_filing_date_count_not_double_counted":1,
        "forms_all_valid_accessions":{
            "10-Q":2,"10-K":2,"10-K/A":1,"8-K":1,
        },
        "forms_with_reviewable_financial_facts":{"10-Q":1,"10-K":1},
        "forms_without_financial_facts":{
            "10-Q":1,"10-K":1,"10-K/A":1,"8-K":1,
        },
    }))
    return db,sec,phase24h


class TestPhase24i(unittest.TestCase):
    def test_splits_2024_2025_from_older_financial_forms_without_writes(self):
        with TemporaryDirectory() as d:
            db,sec,prior=fixture(Path(d))
            old=hashlib.sha256(db.read_bytes()).hexdigest()
            r=analyze(db,sec,prior)
            self.assertEqual(r["total_valid_SEC_accessions"],6)
            self.assertEqual(r["total_valid_10K_10Q_including_amendments"],5)
            self.assertEqual(r["all_years_no_fact_financial_forms"],{
                "10-Q":1,"10-K/A":1,"10-K":1,
            })
            self.assertEqual(r["financial_filings_no_fact_in_target_window_by_form"],{
                "10-Q":1,"10-K/A":1,
            })
            self.assertEqual(r["financial_filings_no_fact_in_target_window_count"],2)
            self.assertEqual(r["financial_no_fact_before_or_after_window_by_year"],{
                "2022":1,
            })
            self.assertEqual(r["accepted_UTC_before_filing_date_source_count"],1)
            self.assertFalse(r["date_conflicts_automatically_fixed"])
            self.assertFalse(r["database_modified"])
            self.assertEqual(hashlib.sha256(db.read_bytes()).hexdigest(),old)

    def test_no_backup_creation_and_fail_closed(self):
        with TemporaryDirectory() as d:
            db,sec,prior=fixture(Path(d))
            missing=Path(d)/"fake.sqlite"
            with self.assertRaisesRegex(ValueError,"OFFLINE_BACKUP_OR_SEC_SOURCE_MISSING"):
                analyze(missing,sec,prior)
            self.assertFalse(missing.exists())

    def test_old_report_form_count_mismatch_blocks(self):
        with TemporaryDirectory() as d:
            db,sec,prior=fixture(Path(d))
            r=json.loads(prior.read_text())
            r["forms_without_financial_facts"]["10-Q"]=22
            prior.write_text(json.dumps(r))
            with self.assertRaisesRegex(ValueError,"PHASE24H_MISSING_FINANCIAL_FORM_COUNT_CHANGED"):
                analyze(db,sec,prior)

    def test_untrusted_prior_pit_certification_blocks(self):
        with TemporaryDirectory() as d:
            db,sec,prior=fixture(Path(d))
            r=json.loads(prior.read_text())
            r["historical_PIT_certified"]=True
            prior.write_text(json.dumps(r))
            with self.assertRaisesRegex(ValueError,"PHASE24H_SOURCE_NOT_VERIFIED"):
                analyze(db,sec,prior)


if __name__=="__main__":
    unittest.main()
