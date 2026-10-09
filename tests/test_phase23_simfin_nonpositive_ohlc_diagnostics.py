from datetime import date
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.phase21_simfin_price_source_audit import PriceInputBlocked
from scripts.phase23_simfin_nonpositive_ohlc_diagnostics import analyze

CSV = (
    "Ticker;SimFinId;Date;Open;High;Low;Close;Adj. Close;Volume\n"
    "AAA;1;2024-01-02;10;12;0;11;10.8;500\n"
    "AAA;1;2024-01-03;0;12;9;11;10.8;500\n"
    "BBB;2;2024-01-04;0;0;0;0;0;0\n"
    "CCC;3;2024-01-05;10;12;9;-1;0;500\n"
    "AAA;1;2024-01-06;10;12;9;11;10.8;500\n"
    "AAA;1;2023-12-29;10;12;9;11;10.8;500\n"
).encode()


def fixture(root: Path):
    source = root / "simfin-source.csv"
    source.write_bytes(CSV)
    report = root / "phase22.json"
    data = {
        "schema": "MERIDYEN_PHASE22_SIMFIN_OHLC_MONTHLY_PIT_QA_V1",
        "status": "RESEARCH_ONLY_OHLC_CAUSE_AND_MONTHLY_PIT_PRICE_COVERAGE_AUDIT",
        "reconciled_phase21_counts": True,
        "verified_months": 21,
        "period": {"start": "2024-01-01", "end": "2025-09-30"},
        "original_price_file_sha256": hashlib.sha256(CSV).hexdigest(),
        "window_rows": 5,
        "window_valid_ohlc_rows": 1,
        "window_strict_invalid_ohlc_rows": 4,
        "invalid_ohlc_reason_counts": {"NONPOSITIVE_OHLC": 4},
    }
    report.write_text(json.dumps(data))
    return source, report


class Phase23NonpositiveOHLCtests(unittest.TestCase):
    def test_reconciles_and_splits_zero_negative_patterns(self):
        with TemporaryDirectory() as d:
            source, report = fixture(Path(d))
            sha_before = hashlib.sha256(source.read_bytes()).hexdigest()
            result = analyze(source, report)
            self.assertEqual(result["window_rows"], 5)
            self.assertEqual(result["window_invalid_ohlc_rows"], 4)
            self.assertEqual(result["window_nonpositive_ohlc_rows"], 4)
            self.assertEqual(result["nonpositive_field_occurrences_not_distinct_rows"], {
                "CLOSE_NEGATIVE": 1, "HIGH_ZERO": 1,
                "LOW_ZERO": 2, "OPEN_ZERO": 2, "CLOSE_ZERO": 1})
            self.assertEqual(result["all_four_ohlc_zero_rows"], 1)
            self.assertEqual(result["nonpositive_rows_with_positive_raw_close"], 2)
            self.assertEqual(
                result["nonpositive_rows_with_positive_close_and_adjusted_close"], 2)
            self.assertEqual(result["monthly_nonpositive_row_counts"],
                             [{"month": "2024-01", "invalid_nonpositive_rows": 4}])
            self.assertEqual(
                result["top_tickers_nonpositive_rows_not_security_identity"][0],
                {"ticker": "AAA", "rows": 2})
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), sha_before)
            self.assertFalse(result["production_database_modified"])
            self.assertEqual(result["rows_deleted"], 0)
            self.assertEqual(result["network_requests"], 0)
            self.assertFalse(result["provider_zero_field_semantics_verified"])

    def test_blocks_changed_source_checksum(self):
        with TemporaryDirectory() as d:
            source, report = fixture(Path(d))
            source.write_bytes(CSV + b"X")
            with self.assertRaisesRegex(PriceInputBlocked, "SOURCE_HASH_MISMATCH"):
                analyze(source, report)

    def test_blocks_report_count_disagreement(self):
        with TemporaryDirectory() as d:
            source, report = fixture(Path(d))
            data = json.loads(report.read_text())
            data["window_strict_invalid_ohlc_rows"] = 5
            report.write_text(json.dumps(data))
            with self.assertRaisesRegex(PriceInputBlocked, "PHASE22_TOTALS_MISMATCH"):
                analyze(source, report)

    def test_blocks_invalid_report_status(self):
        with TemporaryDirectory() as d:
            source, report = fixture(Path(d))
            data = json.loads(report.read_text())
            data["reconciled_phase21_counts"] = False
            report.write_text(json.dumps(data))
            with self.assertRaisesRegex(PriceInputBlocked, "PHASE22_REPORT_NOT_VALIDATED"):
                analyze(source, report)


if __name__ == "__main__":
    unittest.main()
