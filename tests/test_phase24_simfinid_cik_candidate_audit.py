from __future__ import annotations

from datetime import date
import hashlib
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from scripts.phase19_alpha_pit_staging import month_ends
from scripts.phase24_simfinid_cik_candidate_audit import analyze, PriceInputBlocked

SOURCE = "ALPHAVANTAGE_LISTING_STATUS_RESEARCH_ONLY"
CSV = (
    "Ticker;SimFinId;Date;Open;High;Low;Close;Adj. Close;Volume\n"
    "AAA;100;2024-01-02;10;12;9;11;10.5;1000\n"
    "AAA;100;2024-01-03;0;0;0;0;0;0\n"
    "BBB;200;2024-01-04;10;12;9;11;10.5;1000\n"
    "CCC;300;2024-01-05;10;12;9;11;10.5;1000\n"
    "BBB;201;2024-01-06;10;12;9;11;10.5;1000\n"
    "NEW;100;2024-01-07;10;12;9;11;10.5;1000\n"
    "JJJ;500;2024-01-08;10;12;9;11;10.5;1000\n"
    "AAA;100;2023-12-29;10;12;9;11;10.5;1000\n"
).encode()


def fixture(root: Path):
    pit = root / "pit"
    pit.mkdir()
    raw = (
        "symbol,name,exchange,assetType,ipoDate,delistingDate,status\n"
        "AAA,Alpha,NASDAQ,Stock,2020-01-01,null,Active\n"
        "BBB,Beta,NYSE,Stock,2020-01-01,null,Active\n"
        "CCC,Gamma,NASDAQ,Stock,2020-01-01,null,Active\n"
    ).encode()
    sha_pit = hashlib.sha256(raw).hexdigest()
    for d in month_ends(date(2024,1,1),date(2025,9,30)):
        stamp = d.isoformat()
        (pit/(stamp+".csv")).write_bytes(raw)
        (pit/(stamp+".manifest.json")).write_text(json.dumps({
            "as_of":stamp,"source":SOURCE,"sha256":sha_pit,
            "bytes":len(raw),"qualified_stock_rows":3,
            "exchange_counts":{"NASDAQ":2,"NYSE":1,"AMEX":0},
        }))
    source = root/"simfin-daily.csv"
    source.write_bytes(CSV)
    price_sha = hashlib.sha256(CSV).hexdigest()
    current = root/"operational.db"
    con = sqlite3.connect(current)
    try:
        con.execute("""CREATE TABLE security_master (
          security_id TEXT, ticker TEXT, exchange TEXT,
          market TEXT, cik TEXT)""")
        con.executemany("INSERT INTO security_master VALUES(?,?,?,?,?)",[
            ("a","AAA","NASDAQ","US","123"),
            ("b","BBB","NYSE","US",None),
            ("c","CCC","NASDAQ","US","456"),
        ])
        con.commit()
    finally:
        con.close()
    phase20 = root/"phase20.json"
    phase20.write_text(json.dumps({
        "schema":"MERIDYEN_PHASE20_HISTORICAL_IDENTITY_CANDIDATES_V1",
        "status":"CANDIDATES_ONLY_HISTORICAL_IDENTITY_NOT_CERTIFIED",
        "months_verified":21, "distinct_ticker_exchange_listing_keys":3,
        "details":[
            {"ticker": "AAA","exchange":"NASDAQ",
             "category":"CURRENT_TICKER_EXCHANGE_CIK_CANDIDATE",
             "candidate_sample_not_certified":[{"security_id":"a"}]},
            {"ticker":"BBB","exchange":"NYSE",
             "category":"CURRENT_TICKER_EXCHANGE_NO_CIK",
             "candidate_sample_not_certified":[{"security_id":"b"}]},
            {"ticker":"CCC","exchange":"NASDAQ",
             "category":"CURRENT_TICKER_EXCHANGE_CIK_CANDIDATE",
             "candidate_sample_not_certified":[{"security_id":"c"}]},
        ],
    }))
    phase21 = root/"phase21.json"
    phase21.write_text(json.dumps({
        "schema":"MERIDYEN_PHASE21_FREE_SIMFIN_PRICE_AUDIT_V1",
        "status":"SOURCE_COVERAGE_MEASURED_NOT_CANONICAL",
        "period":{"start":"2024-01-01","end":"2025-09-30"},
        "original_file_sha256":price_sha,
        "source_counts":{
            "all_source_rows":8, "window_rows":7,
            "window_valid_ohlc_rows":6, "window_invalid_ohlc_rows":1,
            "period_unique_tickers_also_in_21_month_PIT":3,
        },
    }))
    phase23 = root/"phase23.json"
    phase23.write_text(json.dumps({
        "schema":"MERIDYEN_PHASE23_SIMFIN_NONPOSITIVE_OHLC_TRIAGE_V1",
        "status":"RESEARCH_ONLY_NONPOSITIVE_OHLC_FIELD_CAUSES_MEASURED",
        "source_file_sha256":price_sha,
        "period":{"start":"2024-01-01","end":"2025-09-30"},
        "reconciled_against_phase22":True,
    }))
    return source,pit,current,phase20,phase21,phase23


class Phase24SecurityCrosswalkTests(unittest.TestCase):
    def test_candidate_classification_never_certifies_historical_link(self):
        with TemporaryDirectory() as d:
            root=Path(d)
            inputs=fixture(root)
            before=hashlib.sha256(inputs[2].read_bytes()).hexdigest()
            r=analyze(*inputs)
            after=hashlib.sha256(inputs[2].read_bytes()).hexdigest()
            self.assertEqual(before,after)
            self.assertTrue(r["reconciled_phase19_20_21_23"])
            self.assertEqual(r["phase20_listing_keys"],3)
            self.assertEqual(r["phase21_window_ticker_overlap"],3)
            self.assertEqual(r["simfin_ids_in_window"],5)
            self.assertEqual(r["ticker_strings_with_multiple_simfin_ids"],1)
            self.assertEqual(r["simfin_ids_with_multiple_ticker_strings"],1)
            self.assertEqual(r["review_classes"]["SIMFIN_ID_MULTIPLE_TICKERS_REVIEW"],1)
            self.assertEqual(r["review_classes"]["TICKER_MULTIPLE_SIMFIN_IDS_REVIEW"],2)
            self.assertEqual(r["review_classes"][
                "ONE_PRESENT_DAY_SEC_CIK_CANDIDATE_NOT_HISTORICAL_PROOF"],1)
            self.assertEqual(r["review_classes"]["NO_SEC_CIK_CANDIDATE"],1)
            records={x["SimFinId"]:x for x in r["candidate_records"]}
            self.assertEqual(records["300"]["candidate_CIKs_NOT_verified"],["0000000456"])
            self.assertFalse(records["300"]["certified_historical_SimFinId_CIK"])
            self.assertEqual(records["100"]["strict_invalid_OHLC_rows"],1)
            self.assertEqual(records["100"]["ticker_strings"],["AAA","NEW"])
            self.assertEqual(r["historical_identity_certifications"],0)
            self.assertFalse(r["historical_SimFinId_CIK_crosswalk_written_to_production"])
            self.assertFalse(r["original_SEC_or_price_data_modified"])
            self.assertEqual(r["network_calls"],0)

    def test_source_mutation_fail_closes(self):
        with TemporaryDirectory() as d:
            root=Path(d)
            inputs=list(fixture(root))
            inputs[0].write_bytes(CSV+b"added row")
            with self.assertRaisesRegex(PriceInputBlocked,
                                        "SIMFIN_ORIGINAL_PRICE_SOURCE_CHANGED"):
                analyze(*inputs)

    def test_prior_phase20_listing_mismatch_blocks(self):
        with TemporaryDirectory() as d:
            root=Path(d)
            inputs=list(fixture(root))
            prior=inputs[3]
            payload=json.loads(prior.read_text())
            payload["details"]=payload["details"][:2]
            prior.write_text(json.dumps(payload))
            with self.assertRaisesRegex(PriceInputBlocked,
                                        "PHASE20_LISTING_COUNT_MISMATCH"):
                analyze(*inputs)

    def test_db_missing_does_not_create_file(self):
        with TemporaryDirectory() as d:
            root=Path(d)
            inputs=list(fixture(root))
            missing=root/"missing.db"
            inputs[2]=missing
            with self.assertRaisesRegex(PriceInputBlocked,
                                        "INSTALLED_DB_MISSING"):
                analyze(*inputs)
            self.assertFalse(missing.exists())


if __name__=="__main__":
    unittest.main()
