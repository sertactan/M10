from __future__ import annotations

from datetime import date
import hashlib
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from scripts.phase20_identity_candidate_review import run

SOURCE = "ALPHAVANTAGE_LISTING_STATUS_RESEARCH_ONLY"


def stage_month(root, stamp, entries):
    lines = ["symbol,name,exchange,assetType,ipoDate,delistingDate,status"]
    for ticker, name, exchange in entries:
        lines.append(f"{ticker},{name},{exchange},Stock,2020-01-01,null,Active")
    payload = ("\n".join(lines) + "\n").encode()
    (root / (stamp + ".csv")).write_bytes(payload)
    by_exchange = {e: sum(1 for x in entries if x[2] == e)
                   for e in ("NASDAQ", "NYSE", "AMEX")}
    (root / (stamp + ".manifest.json")).write_text(json.dumps({
        "as_of": stamp, "source": SOURCE,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload), "qualified_stock_rows": len(entries),
        "exchange_counts": by_exchange,
    }), encoding="utf-8")


def fixture_db(db: Path):
    c = sqlite3.connect(db)
    try:
        c.execute("""CREATE TABLE security_master (
            security_id TEXT, ticker TEXT, name TEXT, exchange TEXT,
            market TEXT, cik TEXT)""")
        c.executemany("INSERT INTO security_master VALUES(?,?,?,?,?,?)", [
            ("sidA", "AAA", "Alpha", "NASDAQ", "US", "0000000123"),
            ("sidB", "BBB", "Beta", "NYSE", "US", None),
            ("sidC", "CCC", "Crossed", "NASDAQ", "US", "456"),
            ("sidD", "OLD", "Aliasco", "NYSE", "US", "457"),
            ("sidE", "NEW", "Exact Name Company", "NASDAQ", "US", "458"),
        ])
        c.execute("""CREATE TABLE ticker_aliases(
            alias TEXT, security_id TEXT)""")
        c.execute("INSERT INTO ticker_aliases VALUES ('DDD','sidD')")
        c.commit()
    finally:
        c.close()


class Phase20IdentityCandidateReviewTests(unittest.TestCase):
    def test_reports_categories_and_does_not_mutate_sqlite(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            db = root / "operational.db"
            fixture_db(db)
            items = [
                ("AAA", "Alpha", "NASDAQ"), # direct with CIK
                ("BBB", "Beta", "NYSE"), # direct missing CIK
                ("CCC", "Crossed", "NYSE"), # same ticker other exchange
                ("DDD", "Aliasco", "AMEX"), # alias
                ("EEE", "Exact Name Company", "AMEX"), # exact name only
                ("FFF", "No Local Evidence", "NYSE"), # unresolved
            ]
            stage_month(root, "2024-01-31", items)
            stage_month(root, "2024-02-29", items[:1] + [items[-1], items[-1]])
            before = hashlib.sha256(db.read_bytes()).hexdigest()
            report = run(root, db, date(2024, 1, 1), date(2024, 2, 29))
            after = hashlib.sha256(db.read_bytes()).hexdigest()
            self.assertEqual(before, after)
            self.assertEqual(report["months_verified"], 2)
            self.assertEqual(report["distinct_ticker_exchange_listing_keys"], 6)
            self.assertEqual(report["duplicates_across_months"], 1)
            self.assertEqual(sum(report["categories"].values()), 6)
            self.assertEqual(report["categories"]["CURRENT_TICKER_EXCHANGE_CIK_CANDIDATE"], 1)
            self.assertEqual(report["categories"]["CURRENT_TICKER_EXCHANGE_NO_CIK"], 1)
            self.assertEqual(report["categories"]["OTHER_EXCHANGE_TICKER_CANDIDATE"], 1)
            self.assertEqual(report["categories"]["ALIAS_TICKER_CANDIDATE"], 1)
            self.assertEqual(report["categories"]["NORMALIZED_NAME_CANDIDATE"], 1)
            self.assertEqual(report["categories"]["NO_LOCAL_IDENTITY_CANDIDATE"], 1)
            self.assertFalse(report["historical_cik_figi_mapping_certified"])
            self.assertFalse(report["database_modified"])
            self.assertFalse(report["backtest_ready"])

    def test_tampered_staged_csv_blocks_before_db_lookup(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            db = root / "operational.db"
            fixture_db(db)
            stage_month(root, "2024-01-31", [("AAA", "Alpha", "NASDAQ")])
            (root / "2024-01-31.csv").write_bytes(b"modified!")
            with self.assertRaisesRegex(ValueError, "PIT_SOURCE_AUDIT_NOT_VERIFIED"):
                run(root, db, date(2024, 1, 1), date(2024, 1, 31))

    def test_missing_db_not_silently_created(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            db = root / "missing.db"
            stage_month(root, "2024-01-31", [("AAA", "Alpha", "NASDAQ")])
            with self.assertRaisesRegex(ValueError, "INSTALLED_DB_NOT_FOUND_OR_SYMLINK"):
                run(root, db, date(2024, 1, 1), date(2024, 1, 31))
            self.assertFalse(db.exists())


if __name__ == "__main__":
    unittest.main()
