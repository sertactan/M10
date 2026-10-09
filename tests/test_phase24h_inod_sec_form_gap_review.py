import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from data.database.sqlite_store import SQLiteStore
from scripts.phase14_sec_submissions_archive_reconcile import reconcile
from scripts.phase24h_inod_sec_form_gap_review import analyze

CIK = "0000903651"
NOW = "2026-10-09T01:00:00+00:00"


def _fixture(root: Path):
    db=root/"backup.db"
    store=SQLiteStore(db)
    store.initialize()
    try:
        with store.connection:
            store.connection.execute(
                """INSERT INTO security_master
                  (security_id,ticker,name,exchange,market,cik,created_at,updated_at)
                  VALUES ('S1','INOD','Innodata','NASDAQ','US',?,?,?)""",
                (CIK,NOW,NOW))
            store.connection.execute(
                """INSERT INTO fundamental_facts_source
                (fact_id,security_id,metric_name,provider_metric_name,value,
                 unit,period_end,period_kind,filing_date,accepted_at,
                 available_at,source,source_document,accession_number,
                 retrieved_at,quality_status,validation_status,family,form_type)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                ("F1","S1","REVENUE","Revenue",100,"USD","2024-01-31",
                 "QUARTERLY","2024-02-02",None,
                 "2024-02-03T01:00:00+00:00","SEC_EDGAR",
                 "https://data.sec.gov",f"{CIK}-24-000001",
                 NOW,"AUTHORITATIVE","SEC_CANONICAL","REGULATORY","10-Q"))
    finally:
        store.close()

    sec=root/"sec"
    sec.mkdir()
    valid = [f"{CIK}-24-{i:06d}" for i in range(1,1002)]
    forms=["10-Q"] + ["8-K"]*1000
    root_ids=valid[:3]+[f"{CIK}-24-004000"]
    archive_ids=valid[3:]
    def payload(ids,forms):
        return {
            "accessionNumber":ids,
            "acceptanceDateTime":[
                "2024-01-31T17:00:00Z" if acc.endswith("004000")
                else "2024-02-02T20:00:00Z" for acc in ids],
            "form":forms,
            "filingDate":["2024-02-02"]*len(ids),
        }
    archive_name=f"CIK{CIK}-submissions-001.json"
    (sec/f"CIK{CIK}.json").write_text(json.dumps({
        "cik":int(CIK),
        "filings":{"recent":payload(root_ids,
                  forms[:3]+["8-K"]),
                  "files":[{"name":archive_name}]},
    }))
    (sec/archive_name).write_text(json.dumps(payload(archive_ids,forms[3:])))

    first=root/"first.json"
    tail=root/"tail.json"
    first.write_text(json.dumps(reconcile(
        db,sec,max_issuers=1,max_accessions=1000,accession_offset=0)))
    tail.write_text(json.dumps(reconcile(
        db,sec,max_issuers=1,max_accessions=1000,accession_offset=1000)))
    return db,sec,first,tail


class TestPhase24h(unittest.TestCase):
    def test_classifies_unmatched_8k_and_does_not_count_global_error_twice(self):
        with TemporaryDirectory() as d:
            db,sec,first,tail=_fixture(Path(d))
            sha=hashlib.sha256(db.read_bytes()).hexdigest()
            r=analyze(db,sec,first,tail)
            self.assertEqual(r["valid_accessions_total"],1001)
            self.assertEqual(r["reviewable_accessions_total"],1)
            self.assertEqual(r["total_without_matching_facts"],1000)
            self.assertEqual(r["forms_without_financial_facts"],{"8-K":1000})
            self.assertEqual(r["forms_with_reviewable_financial_facts"],{"10-Q":1})
            self.assertEqual(r["source_before_filing_date_count_not_double_counted"],1)
            self.assertEqual(r["source_before_filing_date_forms"],{"8-K":1})
            self.assertFalse(r["database_modified"])
            self.assertEqual(hashlib.sha256(db.read_bytes()).hexdigest(),sha)

    def test_blocks_prior_report_from_different_db(self):
        with TemporaryDirectory() as d:
            db,sec,first,tail=_fixture(Path(d))
            obj=json.loads(tail.read_text())
            obj["database"]="/another/missing.db"
            tail.write_text(json.dumps(obj))
            with self.assertRaisesRegex(ValueError,"PRIOR_RECONCILIATION_PAGINATION_INCONSISTENT"):
                analyze(db,sec,first,tail)

    def test_blocks_misrepresented_pagination(self):
        with TemporaryDirectory() as d:
            db,sec,first,tail=_fixture(Path(d))
            obj=json.loads(tail.read_text())
            obj["next_accession_offset"]=2000
            tail.write_text(json.dumps(obj))
            with self.assertRaisesRegex(ValueError,"PRIOR_RECONCILIATION_PAGINATION_INCONSISTENT"):
                analyze(db,sec,first,tail)


if __name__=="__main__":
    unittest.main()
