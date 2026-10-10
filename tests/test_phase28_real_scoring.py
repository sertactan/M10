"""Only synthetic regression fixtures; NEVER report these as genuine ticker scores."""
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import sqlite3
import tempfile
import unittest

from app.phase28_real_scoring import (
    SCHEMA, _stage, _valid, coverage_audit, financial_features, run_phase28,
)

NOW = datetime(2026, 10, 10, 16, 0, tzinfo=timezone.utc)


def fact(metric, value, start, end, kind, *,
         available="2026-08-07T00:00:00+00:00", accession="TEST-10Q", unit="USD"):
    return dict(metric=metric, value=value, unit=unit,
                period_start=start, period_end=end, period_kind=kind,
                filing_date="2026-08-06",accepted_at=None,
                available_at=available,source="SEC_EDGAR_LOCAL_ARCHIVE_ACCEPTED_UNVERIFIED",
                source_ref="https://data.sec.gov/test/companyfacts.json",
                accession=accession, form_type="10-Q", evidence_hash="ab"*32)


def example_facts():
    return [
        fact("REVENUE",100,"2024-01-01","2024-12-31","ANNUAL",available="2025-02-27T00:00:00+00:00",accession="2025-K"),
        fact("REVENUE",130,"2025-01-01","2025-12-31","ANNUAL",available="2026-02-27T00:00:00+00:00",accession="2026-K"),
        fact("REVENUE",70,"2026-01-01","2026-03-31","QUARTER",available="2026-05-08T00:00:00+00:00"),
        fact("REVENUE",90,"2026-04-01","2026-06-30","QUARTER"),
        fact("NET_INCOME",18,"2026-04-01","2026-06-30","QUARTER"),
        fact("NET_INCOME",1000,"2025-01-01","2025-06-30","YTD",accession="PREV-10Q"),
        fact("OPERATING_INCOME",20,"2026-01-01","2026-06-30","YTD"),
        fact("REVENUE",160,"2026-01-01","2026-06-30","YTD"),
        fact("OPERATING_CASH_FLOW",40,"2026-01-01","2026-06-30","YTD"),
        fact("CAPEX",5,"2026-01-01","2026-06-30","YTD"),
        fact("NET_INCOME",25,"2026-01-01","2026-06-30","YTD"),
        fact("SBC",10,"2026-01-01","2026-06-30","YTD"),
        fact("CASH",50,None,"2026-06-30","INSTANT"),
        fact("EQUITY",100,None,"2026-06-30","INSTANT"),
        fact("CURRENT_ASSETS",80,None,"2026-06-30","INSTANT"),
        fact("CURRENT_LIABILITIES",20,None,"2026-06-30","INSTANT"),
        fact("SHARES_OUTSTANDING",120,None,"2026-07-31","INSTANT",unit="shares"),
        fact("SHARES_OUTSTANDING",100,None,"2025-07-31","INSTANT",
             available="2025-08-07T00:00:00+00:00",accession="PREV-10Q",unit="shares"),
    ]


class Phase28Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_period_matched_actual_arithmetic(self):
        f = financial_features(example_facts(), NOW)
        self.assertAlmostEqual(f["REVENUE_ANNUAL_YOY"]["value"], .30)
        self.assertAlmostEqual(f["REVENUE_QOQ"]["value"], 90/70-1)
        self.assertAlmostEqual(f["NET_MARGIN_Q"]["value"], .20)
        self.assertAlmostEqual(f["FCF_YTD_USD"]["value"], 35)
        self.assertAlmostEqual(f["FCF_MARGIN_YTD"]["value"], 35/160)
        self.assertAlmostEqual(f["CASH_CONVERSION_YTD"]["value"], 40/25)
        self.assertAlmostEqual(f["SBC_REVENUE_RATIO_YTD"]["value"], 10/160)
        self.assertAlmostEqual(f["WORKING_CAPITAL_USD"]["value"], 60)
        self.assertAlmostEqual(f["CURRENT_RATIO"]["value"], 4)
        self.assertAlmostEqual(f["SHARES_DILUTION_1Y_APPROX"]["value"], .20)
        self.assertEqual(f["F54_DIL_RESEARCH_LEG"]["value"], 0)
        self.assertEqual(f["D01_REVENUE_GROWTH_1Y_LEG"]["value"], 75)
        self.assertTrue(all(x["quality_status"].startswith("RESEARCH_ONLY") for x in f.values()))
        self.assertTrue(all(x["evidence_hash"] for x in f.values()))

    def test_no_division_by_unknowns_or_fiscal_mismatch(self):
        facts=[x for x in example_facts()
               if x["metric"] not in ("CAPEX", "EQUITY", "CURRENT_LIABILITIES")]
        f=financial_features(facts,NOW)
        self.assertNotIn("FCF_YTD_USD",f)
        self.assertNotIn("ROE_YTD_UNANNUALIZED",f)
        self.assertNotIn("WORKING_CAPITAL_USD",f)
        self.assertNotIn("EV_SALES",f)
        self.assertNotIn("ROIC",f)
        self.assertNotIn("S14",f)

    def test_future_and_source_rejected(self):
        x=fact("REVENUE",100,"2025-01-01","2025-12-31","ANNUAL")
        self.assertTrue(_valid(x,NOW))
        self.assertFalse(_valid({**x,"available_at":"2027-01-01T00:00:00+00:00"},NOW))
        self.assertFalse(_valid({**x,"available_at":None},NOW))
        self.assertFalse(_valid({**x,"source":"RESEARCH_USER_GUESS"},NOW))
        self.assertFalse(_valid({**x,"filing_date":"2027-01-01"},NOW))
        self.assertFalse(_valid({**x,"period_end":"2027-12-31"},NOW))
        self.assertFalse(_valid({**x,"evidence_hash":None},NOW))

    def test_models_cannot_become_canonical_from_raw_accounts(self):
        f=financial_features(example_facts(),NOW)
        audits,diag=coverage_audit("INOD",62.04,NOW,f)
        self.assertEqual(len(audits),20)
        self.assertEqual(sum(x["score"] is not None for x in audits),0)
        by={x["model"]:x for x in audits}
        self.assertEqual(by["S14"]["required"],6)
        self.assertEqual(by["S14"]["present"],0)
        self.assertEqual(by["S3"]["required"],3)
        self.assertEqual(by["S16-C"]["required"],22)
        self.assertEqual(by["S16-C"]["present"],0)
        self.assertIsNone(by["S16-E"]["score"])
        self.assertEqual(by["S16-E"]["status"],"SPEC_MISSING")
        self.assertEqual(diag["component_scope"],"INCOMPLETE_RESEARCH_DIAGNOSTIC_NOT_A_MODEL_SCORE")
        self.assertLess(diag["discovery_inputs_present"],48)

    def test_stage_refuses_non_stage_db_without_touching_bytes(self):
        path=self.root/"phase28"/"user.db"
        path.parent.mkdir()
        with closing(sqlite3.connect(path)) as db:
            db.execute("CREATE TABLE user_records(secret TEXT)")
            db.execute("INSERT INTO user_records VALUES ('untouched')")
            db.commit()
        before=hashlib.sha256(path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError,"unrecognized"):
            _stage(path)
        self.assertEqual(before,hashlib.sha256(path.read_bytes()).hexdigest())
        with self.assertRaisesRegex(ValueError,"isolated"):
            _stage(self.root/"operational.db")

    def _staged_sources(self):
        phase27=self.root/"phase27"/"source.db"
        phase27.parent.mkdir()
        with closing(sqlite3.connect(phase27)) as db:
            db.executescript("""
            CREATE TABLE stock_runs(ticker TEXT,quote_status TEXT,quote_price REAL,
              quote_time TEXT,quote_currency TEXT,financial_period TEXT,checked_at TEXT,
              security_id TEXT);
            CREATE TABLE research_facts(ticker TEXT,metric TEXT,value REAL,unit TEXT,
              period_start TEXT,period_end TEXT,period_kind TEXT,filing_date TEXT,
              accepted_at TEXT,available_at TEXT,source TEXT,source_ref TEXT,
              accession TEXT,form_type TEXT,evidence_hash TEXT);
            CREATE TABLE research_features(ticker TEXT,feature_key TEXT,value REAL,
              as_of TEXT,available_at TEXT,source TEXT,source_ref TEXT,
              evidence_hash TEXT,quality_status TEXT);
            """)
            db.execute("INSERT INTO stock_runs VALUES (?,?,?,?,?,?,?,?)",
                       ("INOD","SUCCESS",62.04,"2026-10-09T20:00:01+00:00","USD",
                        "2026-06-30",NOW.isoformat(),"UNIT-TEST-ID"))
            for row in example_facts():
                db.execute("INSERT INTO research_facts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                           ("INOD",row["metric"],row["value"],row["unit"],
                            row["period_start"],row["period_end"],row["period_kind"],
                            row["filing_date"],row["accepted_at"],row["available_at"],
                            row["source"],row["source_ref"],row["accession"],
                            row["form_type"],row["evidence_hash"]))
            db.commit()
        archive=self.root/"archive.db"
        with closing(sqlite3.connect(archive)) as db:
            db.executescript("""CREATE TABLE fundamental_facts_source(
                security_id TEXT,metric_name TEXT,value REAL,unit TEXT,period_start TEXT,
                period_end TEXT,period_kind TEXT,filing_date TEXT,accepted_at TEXT,
                available_at TEXT,source TEXT,source_document TEXT,accession_number TEXT,
                form_type TEXT,raw_payload_hash TEXT);""")
            db.commit()
        return phase27,archive

    def test_end_to_end_only_phase28_db_writes(self):
        phase27,archive=self._staged_sources()
        before27=hashlib.sha256(phase27.read_bytes()).hexdigest()
        before_archive=hashlib.sha256(archive.read_bytes()).hexdigest()
        stage=self.root/"phase28"/"analysis.db"
        report=run_phase28(phase27,stage,archive)
        self.assertEqual(report["ticker"],"INOD")
        self.assertEqual(report["full_model_score_count"],0)
        self.assertIn("S16-C", [r["model"] for r in report["models"]])
        self.assertAlmostEqual(report["features"]["PS_LAST_ANNUAL_RESEARCH"]["value"],
                               62.04*120/130)
        self.assertEqual(before27,hashlib.sha256(phase27.read_bytes()).hexdigest())
        self.assertEqual(before_archive,hashlib.sha256(archive.read_bytes()).hexdigest())
        again=run_phase28(phase27,stage,archive)
        self.assertEqual(again["full_model_score_count"],0)
        with closing(sqlite3.connect(stage)) as db:
            self.assertEqual(db.execute("SELECT schema FROM phase28_meta").fetchone()[0],SCHEMA)
            self.assertEqual(db.execute("SELECT count(*) FROM phase28_runs").fetchone()[0],1)
            self.assertEqual(db.execute("SELECT count(*) FROM scored_models").fetchone()[0],20)
            self.assertEqual(db.execute("SELECT count(*) FROM sourced_features").fetchone()[0],
                             len(report["features"]))

    def test_phase27_ui_overlay_offline_and_provenance(self):
        import os
        os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
        from PySide6.QtWidgets import QApplication
        from app.ui.phase27_current_page import Phase27CurrentPage
        app=QApplication.instance() or QApplication([])
        phase27,archive=self._staged_sources()
        # Phase27 UI requires full JSON stock-run; populate minimal compatible
        # payload from a source-like record, no external network request.
        stage=self.root/"phase28"/"analysis.db"
        run_phase28(phase27,stage,archive)
        with closing(sqlite3.connect(phase27)) as db:
            payload={"ticker":"INOD","price":62.04,"currency":"USD",
                     "trade_date":"2026-10-09","quote_time":"2026-10-09T20:00:01+00:00",
                     "quote_status":"SUCCESS","financial_status":"CACHED_RESEARCH_ONLY",
                     "financial_period":"2026-06-30","bars":251,
                     "raw_research_features":1,"model_audits":[],
                     "price_provider":"YAHOO_COMPAT_RESEARCH",
                     "price_payload_sha256":"a"*64,"research_features":{}}
            db.execute("ALTER TABLE stock_runs ADD COLUMN details_json TEXT")
            db.execute("UPDATE stock_runs SET details_json=?",(json.dumps(payload),))
            db.commit()
        ui=Phase27CurrentPage(phase27,archive,phase28_db=stage)
        self.assertTrue(ui.load_cached("INOD"))
        self.assertIn("PHASE28",ui.summary.text())
        self.assertEqual(ui.table.rowCount(),20)
        self.assertTrue(all(ui.table.item(i,1).text()=="N/A"
                            for i in range(ui.table.rowCount())))
        ui.table.selectRow(0)
        ui.show_details()
        self.assertIn("missing",ui.details.toPlainText())
        ui.close()


if __name__=="__main__":
    unittest.main()
