from __future__ import annotations

from argparse import Namespace
from datetime import date
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.phase19_free_sec_shard import (
    CATALOG_URL, FACTS_ROOT, IntakeBlocked, catalog_rows, fact_dates, run,
)


def args(out, *, execute=True):
    return Namespace(
        start="2024-01-01", end="2025-09-30",
        shard_index=0, shard_size=2, max_total_mib=2,
        max_source_mib=1, pause=0.5, out_dir=Path(out), execute=execute,
    )


CATALOG = json.dumps({
    "fields": ["cik", "name", "ticker", "exchange"],
    "data": [[123, "A", "AAA", "NASDAQ"], [456, "B", "BBB", "NYSE"],
             [789, "C", "CCC", "OTC"]],
}).encode()


def facts(cik):
    return json.dumps({
        "cik": cik,
        "facts": {"us-gaap": {"Revenues": {"units": {"USD": [
            {"filed": "2024-06-01", "end": "2024-03-31", "val": 10},
            {"filed": "2026-06-01", "end": "2024-03-31", "val": 20},
        ]}}}},
    }).encode()


class SecShardTests(unittest.TestCase):
    def test_catalog_excludes_otc_and_cannot_be_pit(self):
        self.assertEqual([r["cik"] for r in catalog_rows(CATALOG)], [123, 456])

    def test_source_filing_window_does_not_use_future_filed(self):
        self.assertEqual(
            fact_dates(facts(123), 123, date(2024, 1, 1), date(2025, 9, 30))
            ["source_fact_rows_filed_in_window"], 1,
        )
        with self.assertRaises(IntakeBlocked):
            fact_dates(facts(123), 999, date(2024, 1, 1), date(2025, 9, 30))

    def test_preview_makes_no_network_calls(self):
        with tempfile.TemporaryDirectory() as folder:
            def forbidden(*_):
                self.fail("preview accessed external network")
            r = run(args(folder, execute=False), fetch=forbidden)
            self.assertEqual(r["status"], "PREVIEW_ONLY_NO_NETWORK")
            self.assertTrue((Path(folder) / "status.json").exists())

    def test_real_source_resume_without_second_network_request(self):
        calls = []
        def fetch(url, agent, size):
            calls.append(url)
            if url == CATALOG_URL:
                return CATALOG
            if url.startswith(FACTS_ROOT):
                return facts(int(url.rsplit("CIK", 1)[1].split(".", 1)[0]))
            self.fail("Unexpected URL")
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict("os.environ", {"SEC_USER_AGENT": "Meridyen Research contact@company.test"}):
                first = run(args(folder), fetch=fetch, sleep=lambda _: None)
                self.assertEqual(first["status"], "SEC_SOURCE_SHARD_COMPLETE_NOT_PIT_CERTIFIED")
                self.assertEqual(first["downloaded"], 2)
                self.assertEqual(len(calls), 3)
                second = run(args(folder), fetch=lambda *_: self.fail("unnecessary fetch"),
                             sleep=lambda _: None)
                self.assertEqual(second["reused"], 2)
                self.assertFalse(second["historical_pit_certified"])
                self.assertFalse(second["canonical_formula_modified"])
                self.assertFalse(second["model_training_performed"])
                self.assertFalse(second["production_database_modified"])

    def test_modified_artifact_fails_closed(self):
        def fetch(url, *_):
            return CATALOG if url == CATALOG_URL else facts(
                int(url.rsplit("CIK", 1)[1].split(".", 1)[0]))
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict("os.environ", {"SEC_USER_AGENT": "Meridyen Research contact@company.test"}):
                run(args(folder), fetch=fetch, sleep=lambda _: None)
                file = Path(folder) / "companyfacts" / "CIK0000000123.json"
                file.write_text("{}")
                r = run(args(folder), fetch=lambda *_: self.fail("tampered artifact cannot download"),
                        sleep=lambda _: None)
            self.assertEqual(r["status"], "PARTIAL_RESUMABLE_NOT_PIT_CERTIFIED")
            self.assertIn("UNVERIFIED_OR_CHANGED_RESTORED_FILE", r["failed"][0]["detail"])

    def test_execute_without_real_agent_fails_before_network(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict("os.environ", {"SEC_USER_AGENT": ""}):
                r = run(args(folder), fetch=lambda *_: self.fail("network used"))
            self.assertEqual(r["status"], "BLOCKED_OR_PARTIAL_NOT_PIT_CERTIFIED")
            self.assertIn("REAL_SEC_USER_AGENT_REQUIRED", r["failed"][0]["detail"])


if __name__ == "__main__":
    unittest.main()
