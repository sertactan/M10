from datetime import date
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.phase21_simfin_price_source_audit import analyze as phase21
from scripts.phase22_simfin_ohlc_monthly_qa import analyze as phase22, _classify_ohlc
from scripts.phase21_simfin_price_source_audit import PriceInputBlocked

PIT_DATA = (
    "symbol,name,exchange,assetType,ipoDate,delistingDate,status\n"
    "AAA,Alpha,NASDAQ,Stock,2020-01-01,null,Active\n"
    "BBB,Beta,NYSE,Stock,2020-01-01,null,Active\n"
).encode()

CSV_DATA = (
    "Ticker;SimFinId;Date;Open;High;Low;Close;Adj. Close;Volume\n"
    "AAA;1;2024-01-02;10;12;9;11;10.5;1000\n"
    "BBB;2;2024-01-03;11;10;9;9;;1100\n"
    "CCC;3;2024-01-04;10;12;9;8;7.9;1500\n"
    "AAA;1;2024-01-05;10;8;9;11;10.5;800\n"
    "BBB;2;2024-01-08;10;12;9;11;10.5;900\n"
    "AAA;1;2023-12-29;10;12;9;11;10.5;1000\n"
).encode()


def setup(root):
    name = "2024-01-31"
    (root / (name + ".csv")).write_bytes(PIT_DATA)
    (root / (name + ".manifest.json")).write_text(json.dumps({
        "as_of": name, "source": "ALPHAVANTAGE_LISTING_STATUS_RESEARCH_ONLY",
        "sha256": hashlib.sha256(PIT_DATA).hexdigest(),
        "bytes": len(PIT_DATA), "qualified_stock_rows": 2,
        "exchange_counts": {"NASDAQ": 1, "NYSE": 1, "AMEX": 0}
    }))
    input_path = root / "simfin-share-prices.csv"
    input_path.write_bytes(CSV_DATA)
    phase21_report = phase21(input_path, root, date(2024, 1, 1), date(2024, 1, 31))
    audit_file = root / "phase21.json"
    audit_file.write_text(json.dumps(phase21_report))
    return input_path, audit_file


class Phase22QualityAuditTests(unittest.TestCase):
    def test_reconciles_prior_ohlc_and_reports_real_categories(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            source, prior = setup(root)
            report = phase22(source, root, prior, date(2024, 1, 1), date(2024, 1, 31))
            self.assertEqual(report["status"],
                             "RESEARCH_ONLY_OHLC_CAUSE_AND_MONTHLY_PIT_PRICE_COVERAGE_AUDIT")
            self.assertEqual(report["verified_months"], 1)
            self.assertEqual(report["window_rows"], 5)
            self.assertEqual(report["window_valid_ohlc_rows"], 2)
            self.assertEqual(report["window_strict_invalid_ohlc_rows"], 3)
            self.assertEqual(report["invalid_ohlc_reason_counts"],
                             {"OPEN_OUTSIDE_RANGE": 1,
                              "CLOSE_OUTSIDE_RANGE": 1, "LOW_EXCEEDS_HIGH": 1})
            self.assertEqual(report["window_rows_ticker_in_same_month_end_listing"], 4)
            self.assertEqual(report["window_listed_ticker_valid_ohlc_positive_adj_rows"], 2)
            self.assertEqual(
                report["per_month"][0]["listed_tickers_with_valid_prices_in_same_calendar_month"],
                2)
            self.assertEqual(
                report["per_month"][0]["listed_tickers_without_valid_prices_in_same_calendar_month"],
                0)
            self.assertFalse(report["ticker_year_month_overlap_is_historical_identity_proof"])
            self.assertFalse(report["production_database_modified"])
            self.assertEqual(report["network_requests"], 0)

    def test_rejects_changed_input_without_restoring_or_redownloading(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            source, prior = setup(root)
            source.write_bytes(CSV_DATA + b"AAA;1;2024-01-30;1;1;1;1;1;0\n")
            with self.assertRaisesRegex(PriceInputBlocked,
                                        "PHASE21_PRICE_INPUT_HASH_MISMATCH"):
                phase22(source, root, prior, date(2024, 1, 1),
                        date(2024, 1, 31))

    def test_rejects_bad_pit_checksum(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            source, prior = setup(root)
            (root / "2024-01-31.csv").write_text("tampered")
            with self.assertRaisesRegex(PriceInputBlocked,
                                        "PHASE19_PIT_ARCHIVE_NOT_VERIFIED"):
                phase22(source, root, prior, date(2024, 1, 1),
                        date(2024, 1, 31))

    def test_ohlc_classifier_prioritizes_non_numeric_and_nonpositive(self):
        cols = {k:k for k in ("open","high","low","close")}
        self.assertEqual(
            _classify_ohlc({"open":"BAD","high":"10","low":"9","close":"10"},cols),
            "NON_NUMERIC_OHLC")
        self.assertEqual(
            _classify_ohlc({"open":"0","high":"10","low":"9","close":"10"},cols),
            "NONPOSITIVE_OHLC")
        self.assertEqual(
            _classify_ohlc({"open":"10","high":"inf","low":"9","close":"10"},cols),
            "NON_FINITE_OHLC")


if __name__ == "__main__":
    unittest.main()
