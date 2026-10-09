import hashlib,json,sqlite3
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.phase19_alpha_pit_staging import month_ends
from scripts.phase25q_isolated_source_pit_stage import build, SCHEMA, LABEL


def fixture(root:Path):
    pit=root/"pit";pit.mkdir()
    for day in month_ends(date(2024,1,1),date(2025,9,30)):
        key=day.isoformat()
        body=b"symbol,name,exchange,assetType,ipoDate,delistingDate,status\nA,Agilent Technologies Inc,NYSE,Stock,1999-11-18,null,Active\n"
        (pit/(key+".csv")).write_bytes(body)
        manifest={"source":"ALPHAVANTAGE_LISTING_STATUS_RESEARCH_ONLY",
                  "as_of":key,"sha256":hashlib.sha256(body).hexdigest(),
                  "qualified_stock_rows":1,"retrieved_utc":"2026-10-09T00:00:00Z",
                  "bytes":len(body),"historical_pit_identity_certified":False,
                  "stable_cik_or_figi_mapping_verified":False}
        (pit/(key+".manifest.json")).write_text(json.dumps(manifest))
    price=root/"source.csv"
    price.write_text(
        "Ticker;SimFinId;Date;Open;High;Low;Close;Adj. Close;Volume;Dividend;Shares Outstanding\n"
        "A;1234;2024-01-02;100;105;99;102;98;4000;;100000\n"
        "A;1234;2024-01-02;100;105;99;102;98;4000;;100000\n"
        "A;1234;2025-09-30;107;108;101;102;99;4000;0;100000\n"
        "A;1234;2025-10-01;107;108;101;102;99;4000;0;100000\n",encoding="utf-8"
    )
    old=root/"phase24.json"
    old.write_text(json.dumps({
       "status":"SIMFIN_ID_TO_CIK_CANDIDATES_ONLY_ZERO_HISTORICAL_ID_CERTIFICATIONS",
       "period":{"start":"2024-01-01","end":"2025-09-30"},
       "historical_identity_certifications":0,"canonical_price_selections_written":0,
       "source_sha256":hashlib.sha256(price.read_bytes()).hexdigest(),
       "candidate_records":[{"SimFinId":"1234","ticker_strings":["A"],"candidate_CIKs_NOT_verified":["00001000"],
                             "first_price_date":"2024-01-02","last_price_date":"2025-09-30"}]}))
    k=root/"phase25k.json"
    k.write_text(json.dumps({"schema":"MERIDYEN_PHASE25K_FULL_UNIVERSE_CANONICAL_ACCEPTANCE_LEDGER_V1",
       "accepted_canonical_securities":0,"actual_WF9_executed":False,
       "actual_Learning_V3_executed":False,
       "ledger":[{"SimFinId":str(j),"ticker":f"X{j}","priority":"P2",
                  "missing_evidence":"HISTORICAL_CIK_NOT_VERIFIED"} for j in range(133)]}))
    return pit,price,old,k

class TestPhase25Q(unittest.TestCase):
    def test_private_staging_exact_21_provenance_and_reusable(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            pit,price,old,k=fixture(root)
            f={path:path.read_bytes() for path in (price,old,k)}
            stage=root/"stage"
            a=build(pit_dir=pit,source=price,phase24=old,phase25k=k,
                    prod_db=root/"nonexistent_prod.db",out_root=stage)
            self.assertEqual(a["schema"],SCHEMA)
            self.assertEqual(a["status"],LABEL)
            self.assertEqual(a["month_end_snapshots"],21)
            self.assertEqual(a["monthly_membership_rows"],21)
            self.assertEqual(a["source_daily_valid_price_rows"],2)
            self.assertEqual(a["source_duplicate_identity_date_rows_ignored"],1)
            self.assertEqual(a["backtest_eligible_securities"],0)
            self.assertFalse(a["canonical_ready"])
            self.assertFalse(a["Learning_V3_executed"])
            b=build(pit_dir=pit,source=price,phase24=old,phase25k=k,
                    prod_db=root/"nonexistent_prod.db",out_root=stage)
            self.assertEqual(b["staging_version"],a["staging_version"])
            with sqlite3.connect(a["staging_db"]) as con:
                self.assertEqual(con.execute("SELECT COUNT(*) FROM candidate_gate").fetchone()[0],133)
                self.assertEqual(con.execute("SELECT COUNT(*) FROM source_daily_price WHERE listed_in_same_month_end_archive=1").fetchone()[0],2)
            self.assertTrue(Path(a["backup_db"]).is_file())
            self.assertEqual({path:path.read_bytes() for path in f},f)
    def test_detects_monthly_tampering(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            pit,price,old,k=fixture(root)
            (pit/"2024-01-31.csv").write_text("tampered")
            with self.assertRaises(ValueError):
                build(pit_dir=pit,source=price,phase24=old,
                      phase25k=k,prod_db=root/"noprod",out_root=root/"stage")
            self.assertFalse((root/"stage").exists())
if __name__=="__main__":
    unittest.main()
