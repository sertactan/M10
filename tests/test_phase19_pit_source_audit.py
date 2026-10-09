from __future__ import annotations

from datetime import date
import hashlib
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from scripts.phase19_pit_source_audit import audit

SOURCE = "ALPHAVANTAGE_LISTING_STATUS_RESEARCH_ONLY"


def csv(rows):
    head = "symbol,name,exchange,assetType,ipoDate,delistingDate,status\n"
    return (head + "".join(
        f"{symbol},{name},{exchange},Stock,2020-01-01,null,Active\n"
        for symbol, name, exchange in rows
    )).encode()


def save(root, stamp, entries):
    payload = csv(entries)
    path = root / (stamp + ".csv")
    path.write_bytes(payload)
    counts = {
        "NASDAQ": sum(x[2] == "NASDAQ" for x in entries),
        "NYSE": sum(x[2] == "NYSE" for x in entries),
        "AMEX": sum(x[2] == "AMEX" for x in entries),
    }
    manifest = {
        "as_of": stamp, "source": SOURCE, "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload), "qualified_stock_rows": len(entries),
        "exchange_counts": counts,
    }
    (root / (stamp + ".manifest.json")).write_text(json.dumps(manifest))


class Phase19OfflineListingAuditTests(unittest.TestCase):
    def test_verified_source_keys_are_not_unique_issuers(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            save(root, "2024-01-31", [
                ("AAA", "Alpha", "NASDAQ"), ("BBB", "Beta", "NYSE")])
            save(root, "2024-02-29", [
                ("AAA", "Alpha Incorporated", "NASDAQ"), ("CCC", "Gamma", "NYSE")])
            r = audit(root, start=date(2024, 1, 1), end=date(2024, 2, 29))
            self.assertEqual(r["status"], "SOURCE_ARCHIVE_VERIFIED_NOT_PIT_CERTIFIED")
            self.assertEqual(r["verified_months"], 2)
            self.assertEqual(r["distinct_ticker_exchange_listing_keys"], 3)
            self.assertEqual(r["distinct_ticker_strings"], 3)
            self.assertEqual(r["listing_key_with_name_variations"], 1)
            self.assertEqual(
                r["monthly_key_changes_not_delisting_proof"][0]
                ["absent_listing_keys_since_previous_month"], 1
            )
            self.assertFalse(r["original_pit_identity_certified"])
            self.assertFalse(r["model_training_performed"])

    def test_unpaired_and_invalid_sources_block(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            save(root, "2024-01-31", [("AAA", "Alpha", "NASDAQ")])
            r = audit(root, start=date(2024, 1, 1), end=date(2024, 2, 29))
            self.assertEqual(r["verified_months"], 1)
            self.assertEqual(r["status"], "BLOCKED_SOURCE_ARCHIVE_INCOMPLETE_OR_INVALID")
            self.assertTrue(any("MISSING_CSV_OR_MANIFEST" in x for x in r["findings"]))
            (root / "2024-01-31.csv").write_bytes(b"tampered")
            r = audit(root, start=date(2024, 1, 1), end=date(2024, 1, 31))
            self.assertEqual(r["verified_months"], 0)
            self.assertTrue(r["findings"])
            self.assertFalse(r["production_database_modified"])

    def test_duplicate_listing_key_is_not_silently_counted(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            save(root, "2024-01-31", [
                ("AAA", "Alpha", "NASDAQ"), ("AAA", "Alpha duplicate", "NASDAQ")])
            r = audit(root, start=date(2024, 1, 1), end=date(2024, 1, 31))
            self.assertEqual(r["status"], "BLOCKED_SOURCE_ARCHIVE_INCOMPLETE_OR_INVALID")
            self.assertEqual(r["verified_months"], 0)

    def test_optional_installed_db_has_read_only_candidate_matching(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            save(root, "2024-01-31", [
                ("AAA", "Alpha", "NASDAQ"), ("BBB", "Beta", "NYSE"),
                ("CCC", "Gamma", "AMEX"), ("DDD", "Delta", "NASDAQ")])
            db = root / "original.db"
            c = sqlite3.connect(db)
            try:
                c.execute("""CREATE TABLE security_master(
                    ticker TEXT, exchange TEXT, security_id TEXT,
                    cik TEXT, market TEXT)""")
                c.executemany("INSERT INTO security_master VALUES(?,?,?,?,?)", [
                    ("AAA", "NASDAQ", "sid1", "123", "US"),
                    ("BBB", "NYSE", "sid2", "", "US"),
                    ("CCC", "AMEX", "sid3", "333", "US"),
                    ("CCC", "AMEX", "sid4", "444", "US"),
                ])
                c.commit()
            finally:
                c.close()
            before = hashlib.sha256(db.read_bytes()).hexdigest()
            r = audit(root, start=date(2024, 1, 1),
                      end=date(2024, 1, 31), db=db)
            after = hashlib.sha256(db.read_bytes()).hexdigest()
            self.assertEqual(before, after)
            result = r["current_security_master_candidate_match"]
            self.assertEqual(result["matched_single_db_security_id_with_cik"], 1)
            self.assertEqual(result["matched_single_db_security_id_without_cik"], 1)
            self.assertEqual(result["multiple_db_security_ids_same_listing_key"], 1)
            self.assertEqual(result["no_current_db_match"], 1)
            self.assertFalse(result["historical_cik_figi_mapping_certified"])

    def test_missing_db_is_not_created(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            save(root, "2024-01-31", [("AAA", "Alpha", "NASDAQ")])
            db = root / "nonexistent.db"
            r = audit(root, start=date(2024, 1, 1), end=date(2024, 1, 31), db=db)
            self.assertEqual(r["current_security_master_candidate_match"]["status"],
                             "BLOCKED_DB_MISSING_OR_SYMLINK")
            self.assertFalse(db.exists())


if __name__ == "__main__":
    unittest.main()
