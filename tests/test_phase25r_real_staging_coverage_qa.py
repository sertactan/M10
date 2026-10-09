import hashlib,json,sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from scripts.phase19_alpha_pit_staging import month_ends
from scripts.phase25r_real_staging_coverage_qa import analyze

def setup(root):
    pit=root/"pit";pit.mkdir()
    db=root/"research_pit.sqlite";backup=root/"research_pit.backup.sqlite"
    with closing(sqlite3.connect(db)) as con:
        con.executescript("""
        CREATE TABLE source_artifacts(source_key TEXT,source_sha256 TEXT,kind TEXT);
        CREATE TABLE monthly_research_membership(month_end TEXT,ticker TEXT,exchange TEXT);
        CREATE TABLE source_daily_price(simfin_id TEXT,ticker TEXT,trade_date TEXT,listed_in_same_month_end_archive INTEGER,source_adjustment_certified INTEGER);
        CREATE TABLE candidate_identity(simfin_id TEXT,historical_CIK_identity_certified INTEGER);
        CREATE TABLE candidate_gate(simfin_id TEXT);
        """)
        for x in month_ends(date(2024,1,1),date(2025,9,30)):
            stamp=x.isoformat()
            rows=[f"A,First Agilent,NYSE,Stock,1999-11-18,null,Active"]
            if stamp=="2024-01-31":
                rows.append("A,Second Agilent,NYSE,Stock,2000-01-01,null,Active")
            payload=("symbol,name,exchange,assetType,ipoDate,delistingDate,status\n"+
                     "\n".join(rows)+"\n").encode()
            (pit/(stamp+".csv")).write_bytes(payload)
            con.execute("INSERT INTO source_artifacts VALUES(?,?,?)",
               (stamp,hashlib.sha256(payload).hexdigest(),
                "ALPHAVANTAGE_HISTORIC_MONTH_END_RETRIEVED_RETROSPECTIVELY"))
            con.execute("INSERT INTO monthly_research_membership VALUES(?,?,?)",
               (stamp,"A","NYSE"))
        con.executemany("INSERT INTO candidate_identity VALUES(?,0)",
                        [(str(x),) for x in range(5307)])
        con.executemany("INSERT INTO candidate_gate VALUES(?)",
                        [(str(x),) for x in range(133)])
        con.executemany("INSERT INTO source_daily_price VALUES(?,?,?,1,0)",[
           ("1234","A","2024-01-02"),("1234","A","2025-09-30")])
        con.commit()
        with closing(sqlite3.connect(backup)) as out:
            con.backup(out)
    manifest=root/"manifest.json"
    manifest.write_text(json.dumps({
       "schema":"MERIDYEN_PHASE25Q_VERSIONED_RESEARCH_STAGING_V1",
       "status":"RESEARCH_ONLY_NOT_CANONICAL_PIT",
       "period":{"start":"2024-01-01","end":"2025-09-30"},
       "month_end_snapshots":21,"month_end_retrieved_after_backtest_window":True,
       "canonical_ready":False,"backtest_eligible_securities":0,
       "production_DB_modified":False,"source_price_sha256":"1"*64,
       "staging_db":str(db),"backup_db":str(backup),
       "staging_version":"fixture",
       "source_daily_valid_price_rows":2,"monthly_membership_rows":21,
       "source_counts":{"month_snapshot_source_records":22,"invalid_OHLC":0,
                        "nonpositive_adj_or_invalid_volume":0}
    }))
    prior=root/"phase25b.json"
    cohort=[{"SimFinId":"1234","ticker":"A","valid_ohlc_positive_source_adjusted_rows":2}]
    cohort.extend({"SimFinId":str(x+10000),"ticker":f"X{x}",
                   "valid_ohlc_positive_source_adjusted_rows":0}
                  for x in range(3556))
    prior.write_text(json.dumps({
      "schema":"MERIDYEN_PHASE25B_SIMFIN_DISTINCT_DATE_QUALITY_RESEARCH_V1",
      "status":"DISTINCT_SIMFINID_DATE_COUNTS_VERIFIED_RESEARCH_ONLY_NOT_PIT",
      "window":{"start":"2024-01-01","end":"2025-09-30"},
      "canonical_eligible":0,"source_price_file_SHA256":"1"*64,
      "phase25a_prior_candidate_21months":3557,
      "candidate_depth_records":cohort,"metrics":{"valid_source_rows":2}
    }))
    return manifest,prior,pit

class Test25R(unittest.TestCase):
    def test_exact_21_and_quarantine_conflicting_issuer(self):
        with TemporaryDirectory() as td:
            p,b,pit=setup(Path(td))
            r=analyze(p,b,pit)
            self.assertEqual(r["reconciled_strong_candidate_source_valid_rows"],2)
            self.assertEqual(r["conflicting_month_ticker_exchange_identity_rows"],1)
            self.assertEqual(r["conflicting_strong_cohort_tickers"],["A"])
            self.assertFalse(r["actual_Learning_V3_executed"])
            self.assertFalse(r["actual_WF9_executed"])
    def test_source_hash_changed_fails_closed(self):
        with TemporaryDirectory() as td:
            p,b,pit=setup(Path(td))
            (pit/"2024-01-31.csv").write_text("untrusted",encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"SOURCE_MONTH_SHA256"):
                analyze(p,b,pit)
if __name__=="__main__":
    unittest.main()
