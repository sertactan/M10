from datetime import date
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import zipfile

from scripts.phase21_simfin_price_source_audit import analyze, PriceInputBlocked

S = "ALPHAVANTAGE_LISTING_STATUS_RESEARCH_ONLY"


def pit_fixture(root: Path):
    payload = ("symbol,name,exchange,assetType,ipoDate,delistingDate,status\n"
               "AAA,Alpha,NASDAQ,Stock,2020-01-01,null,Active\n"
               "BBB,Beta,NYSE,Stock,2020-01-01,null,Active\n").encode()
    (root / "2024-01-31.csv").write_bytes(payload)
    (root / "2024-01-31.manifest.json").write_text(json.dumps({
        "as_of":"2024-01-31","source":S,
        "sha256":hashlib.sha256(payload).hexdigest(),
        "bytes":len(payload),"qualified_stock_rows":2,
        "exchange_counts":{"NASDAQ":1,"NYSE":1,"AMEX":0},
    }))


SEMICOLON = ("Ticker;SimFinId;Date;Open;High;Low;Close;Adj. Close;Volume\n"
             "AAA;101;2024-01-02;10;12;9;11;10.5;1500\n"
             "AAA;101;2024-01-03;11;12;10;12;11.5;1100\n"
             "AAA;202;2024-01-04;11;12;10;12;11.5;1100\n"
             "CCC;303;2024-01-05;10;12;9;11;10.8;100\n"
             "BBB;404;2024-01-05;9;8;10;11;11;100\n"
             "AAA;101;2023-12-29;10;12;9;11;10.5;1500\n").encode()

COMMA = ("Ticker,Date,Open,High,Low,Close,Volume\n"
         "AAA,2024-01-02,10,12,9,11,1500\n").encode()


class SimFinSourceAuditTests(unittest.TestCase):
    def test_semicolon_price_coverage_simfin_id_risks(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            pit_fixture(root)
            file = root / "shareprices-daily.csv"
            file.write_bytes(SEMICOLON)
            report = analyze(file, root, date(2024,1,1), date(2024,1,31))
            counts = report["source_counts"]
            self.assertEqual(report["status"], "SOURCE_COVERAGE_MEASURED_NOT_CANONICAL")
            self.assertEqual(counts["all_source_rows"], 6)
            self.assertEqual(counts["window_rows"], 5)
            self.assertEqual(counts["window_valid_ohlc_rows"], 4)
            self.assertEqual(counts["window_invalid_ohlc_rows"], 1)
            self.assertEqual(counts["period_unique_ticker_strings"], 3)
            self.assertEqual(counts["period_unique_tickers_also_in_21_month_PIT"], 2)
            self.assertEqual(counts["pit_distinct_tickers_without_price_rows"], 0)
            self.assertEqual(counts["tickers_with_multiple_simfin_ids_in_window"], 1)
            self.assertEqual(counts["window_valid_numeric_adj_close_rows"], 4)
            self.assertFalse(report["adjustment_provenance_independently_verified"])
            self.assertFalse(report["operational_database_modified"])
            self.assertEqual(report["network_calls"], 0)

    def test_zipped_csv_and_no_adjusted_is_not_dual(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            pit_fixture(root)
            archive = root / "simfin-shareprices.zip"
            with zipfile.ZipFile(archive,"w") as f:
                f.writestr("shareprices-us-daily.csv", COMMA)
            report = analyze(archive, root, date(2024,1,1), date(2024,1,31))
            counts = report["source_counts"]
            self.assertFalse(counts["source_adjusted_close_column_present"])
            self.assertEqual(counts["window_valid_numeric_adj_close_rows"], 0)
            self.assertEqual(counts["period_unique_tickers_also_in_21_month_PIT"], 1)

    def test_source_pit_hash_missing_is_blocker(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            pit_fixture(root)
            file = root / "shareprices.csv"
            file.write_bytes(SEMICOLON)
            (root / "2024-01-31.csv").write_bytes(b"tampered")
            with self.assertRaises(PriceInputBlocked):
                analyze(file,root,date(2024,1,1),date(2024,1,31))

    def test_fundamentals_without_prices_rejected(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            pit_fixture(root)
            file = root/"simfin-fundamentals.csv"
            file.write_text("Ticker;Date;Revenue\nAAA;2024-01-31;123\n")
            with self.assertRaisesRegex(PriceInputBlocked, "PRICE_COLUMNS_MISSING"):
                analyze(file,root,date(2024,1,1),date(2024,1,31))

    def test_zip_with_more_than_one_csv_fails_closed(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            pit_fixture(root)
            archive = root/"multiple.zip"
            with zipfile.ZipFile(archive,"w") as f:
                f.writestr("a.csv",COMMA)
                f.writestr("b.csv",COMMA)
            with self.assertRaisesRegex(PriceInputBlocked, "EXACTLY_ONE"):
                analyze(archive,root,date(2024,1,1),date(2024,1,31))


if __name__ == "__main__":
    unittest.main()
