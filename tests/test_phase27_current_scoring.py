"""Synthetic regression fixtures ONLY; real INOD output comes from separate network pilot."""
from datetime import datetime, timezone
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from app.phase27_current_scoring import (
    check_ticker, load_identity, model_matrix, parse_yahoo_chart,
    run_pilot, stage_connect,
)

NOW = datetime(2026, 10, 11, tzinfo=timezone.utc)
BAR = {"trade_date":"2026-10-09", "o":10.0,"h":12.0,"l":9.0,"c":11.0,
       "adjusted":11.0,"volume":500.0,"timestamp":"2026-10-09T13:30:00+00:00"}


def _fixture_archive(path: Path) -> None:
    with closing(sqlite3.connect(path)) as db:
        db.executescript("""
        CREATE TABLE security_master(security_id TEXT, ticker TEXT, cik TEXT, market TEXT);
        INSERT INTO security_master VALUES ('TEST-ID','INOD','0000903651','US');
        CREATE TABLE fundamental_facts_source(
           security_id TEXT,metric_name TEXT,value REAL,unit TEXT,
           period_start TEXT,period_end TEXT,period_kind TEXT,
           filing_date TEXT,accepted_at TEXT,available_at TEXT,source TEXT,
           source_document TEXT,accession_number TEXT,form_type TEXT,
           raw_payload_hash TEXT,quality_status TEXT);
        INSERT INTO fundamental_facts_source VALUES
          ('TEST-ID','REVENUE',100,'USD','2024-01-01','2024-12-31','ANNUAL',
           '2025-02-01',NULL,'2025-02-02T00:00:00+00:00','SEC_EDGAR',
           'https://data.sec.gov/TEST','ACC1','10-K','abcd','AUTHORITATIVE'),
          ('TEST-ID','REVENUE',130,'USD','2025-01-01','2025-12-31','ANNUAL',
           '2026-02-01',NULL,'2026-02-02T00:00:00+00:00','SEC_EDGAR',
           'https://data.sec.gov/TEST','ACC2','10-K','efgh','AUTHORITATIVE');
        """)


class Phase27Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_symbol_gate(self):
        self.assertEqual(check_ticker("inod"), "INOD")
        for value in ("", "../INOD", "INOD?cookie", "a"*22):
            with self.assertRaises(ValueError):
                check_ticker(value)

    def test_yahoo_identity_and_future_gate(self):
        body = {"chart":{"result":[{"meta":{"symbol":"INOD","currency":"USD"},
                "timestamp":[1791552600],
                "indicators":{"quote":[{"open":[10],"high":[12],"low":[9],
                                         "close":[11],"volume":[500]}],
                              "adjclose":[{"adjclose":[10.8]}]}}]}}
        rows, _meta = parse_yahoo_chart(body, "INOD", NOW)
        self.assertEqual(rows[0]["adjusted"], 10.8)
        with self.assertRaisesRegex(ValueError, "Ticker/currency mismatch"):
            parse_yahoo_chart(body, "TMDX", NOW)
        body["chart"]["result"][0]["timestamp"] = [1900000000]
        with self.assertRaisesRegex(ValueError, "Future price"):
            parse_yahoo_chart(body, "INOD", NOW)

    def test_stage_refuses_live_db_path(self):
        with self.assertRaisesRegex(ValueError, "phase27"):
            stage_connect(self.root / "operational.db")
        danger = self.root / "phase27" / "user.db"
        danger.parent.mkdir(parents=True)
        with closing(sqlite3.connect(danger)) as con:
            con.execute("CREATE TABLE private_user_data(secret TEXT)")
            con.execute("INSERT INTO private_user_data VALUES ('keep-me')")
            con.commit()
        with self.assertRaisesRegex(ValueError, "non-Phase27"):
            stage_connect(danger)
        with closing(sqlite3.connect(danger)) as con:
            self.assertEqual(con.execute("SELECT secret FROM private_user_data").fetchone()[0],
                             "keep-me")

    def _piloted(self):
        archive = self.root / "source.db"
        _fixture_archive(archive)
        stage = self.root / "phase27" / "staging.db"
        def fetched(ticker):
            self.assertEqual(ticker, "INOD")
            return [BAR], {"symbol":"INOD","currency":"USD",
                           "regularMarketTime":1791576001}, "a"*64, NOW
        return archive, stage, run_pilot(stage, archive, "INOD", fetch=fetched, as_of=NOW)

    def test_research_pilot_no_canonical_and_no_archive_write(self):
        archive, stage, output = self._piloted()
        before = archive.read_bytes()
        self.assertEqual(output["quote_status"], "SUCCESS")
        self.assertEqual(output["price"], 11)
        self.assertAlmostEqual(output["research_features"]["REVENUE_ANNUAL_YOY"], 0.30)
        self.assertEqual(output["canonical_accepted_securities"], 0)
        self.assertEqual(output["wf9"], "BLOCKED")
        self.assertTrue(all(x["score"] is None for x in output["model_audits"]))
        self.assertEqual(len(next(x["missing"] for x in output["model_audits"]
                            if x["model"] == "S16-C")), 22)
        self.assertEqual(archive.read_bytes(), before)
        with closing(sqlite3.connect(stage)) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM research_bars").fetchone()[0], 1)
            self.assertEqual(con.execute("SELECT COUNT(*) FROM research_facts").fetchone()[0], 2)
            self.assertEqual(con.execute("SELECT COUNT(*) FROM model_audits").fetchone()[0], 20)

    def test_stale_and_provider_error_stay_unscored(self):
        archive=self.root/"history.db"
        _fixture_archive(archive)
        stale = dict(BAR, trade_date="2026-09-30")
        result=run_pilot(self.root/"phase27"/"stale.db",archive,"INOD",
                         fetch=lambda _ticker:([stale],{"currency":"USD",
                         "regularMarketTime":1791576001},"e"*64,NOW),as_of=NOW)
        self.assertEqual(result["quote_status"], "STALE_DATA")
        def broken(_ticker): raise RuntimeError("HTTP 429")
        error=run_pilot(self.root/"phase27"/"error.db",archive,"INOD",fetch=broken,as_of=NOW)
        self.assertEqual(error["quote_status"], "PROVIDER_ERROR")
        self.assertIsNone(error["price"])
        self.assertFalse(any(x["score"] is not None for x in error["model_audits"]))

    def test_provider_error_preserves_last_known_good_cache(self):
        archive, stage, previous = self._piloted()
        def denied(_ticker): raise RuntimeError("HTTP 429")
        later = run_pilot(stage, archive, "INOD", fetch=denied, as_of=NOW)
        self.assertEqual(later["quote_status"], "PROVIDER_ERROR")
        self.assertTrue(later["reused_last_known_good_cache"])
        self.assertEqual(later["price"], previous["price"])
        with closing(sqlite3.connect(stage)) as db:
            self.assertEqual(db.execute(
                "SELECT quote_status FROM stock_runs WHERE ticker='INOD'"
            ).fetchone()[0], "SUCCESS")
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM provider_events WHERE ticker='INOD'"
            ).fetchone()[0], 2)

    def test_null_period_sec_fact_does_not_duplicate_on_retry(self):
        archive = self.root / "source.db"
        _fixture_archive(archive)
        with closing(sqlite3.connect(archive)) as db:
            db.execute("""INSERT INTO fundamental_facts_source VALUES
                ('TEST-ID','SHARES_OUTSTANDING',1000000,'shares',NULL,'2026-07-31',
                 'INSTANT','2026-08-01',NULL,'2026-08-02T00:00:00+00:00','SEC_EDGAR',
                 'https://data.sec.gov/TEST','ACC3','10-Q','h123','AUTHORITATIVE')""")
            db.commit()
        stage = self.root / "phase27" / "staging.db"
        def fetched(_ticker):
            return [BAR],{"symbol":"INOD","currency":"USD",
                          "regularMarketTime":1791576001},"a"*64,NOW
        run_pilot(stage,archive,"INOD",fetch=fetched,as_of=NOW)
        run_pilot(stage,archive,"INOD",fetch=fetched,as_of=NOW)
        with closing(sqlite3.connect(stage)) as db:
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM research_facts WHERE ticker='INOD'"
            ).fetchone()[0],3)
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM provider_events WHERE ticker='INOD'"
            ).fetchone()[0],2)

    def test_current_research_ui_offscreen(self):
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from app.ui.phase27_current_page import Phase27CurrentPage
        _app=QApplication.instance() or QApplication([])
        archive, stage, _out = self._piloted()
        ui=Phase27CurrentPage(stage,archive)
        self.assertTrue(ui.load_cached("INOD"))
        self.assertEqual(ui.table.rowCount(),20)
        self.assertIn("11.00 USD", ui.summary.text())
        rows={ui.table.item(i,0).text(): ui.table.item(i,1).text()
              for i in range(ui.table.rowCount())}
        self.assertEqual(rows["S16-C"], "N/A")
        self.assertEqual(rows["S16-E"], "N/A")
        ui.close()

if __name__ == "__main__":
    unittest.main()
