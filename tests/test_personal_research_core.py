"""Meaningful safety and provenance tests for the isolated Personal engine."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from app.personal_research.contracts import digest
from app.personal_research.evidence_store import EvidenceStore
from app.personal_research.pipeline import analyze
from app.personal_research.quality_aggregator import assess_personal_s14
from app.personal_research.report_builder import export_report
from app.personal_research.source_extractor import load_evidence_packet, verify_source_rows
from app.personal_research.s6_assessed import assess_s6
from core.scoring.s1_s14 import s14


def baseline(root: Path):
    stocks = []
    for symbol in ("INOD", "CRMD", "ETON", "PENG", "TMDX"):
        stocks.append({
            "ticker": symbol, "financial_period": "2025-12-31",
            "models": {"S6": {"acceptance": "N/A", "score": None},
                       "B_Q": {"acceptance": "N/A", "score": None},
                       "S13": {"acceptance": "REVIEW_REQUIRED", "score": None},
                       "S14": {"acceptance": "N/A", "score": None},
                       "S7": {"acceptance": "CURRENT_RESEARCH_FULL", "score": 100},
                       "S11": {"acceptance": "CURRENT_RESEARCH_FULL", "score": 0},
                       "S12": {"acceptance": "CURRENT_RESEARCH_FULL", "score": 91.5}},
        })
    packet = {"stocks": stocks, "full_research_scores": 17,
              "canonical_pit_features": 0, "s16_e_production_enabled": False}
    path = root / ".master_tasks_v12_private/comparison/five_stock_v2.json"
    path.parent.mkdir(parents=True)
    raw = json.dumps(packet, sort_keys=True).encode()
    path.write_bytes(raw)
    Path(str(path) + ".sha256").write_text(hashlib.sha256(raw).hexdigest())
    return path


class PersonalCoreTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root = Path(self.dir.name)
        self.baseline_file = baseline(self.root)

    def test_baseline_remains_identical_and_sidecar_independent(self):
        start = hashlib.sha256(self.baseline_file.read_bytes()).hexdigest()
        result = analyze("INOD", evidence_root=self.root,
                         at=datetime(2026, 10, 12, tzinfo=timezone.utc))
        self.assertEqual(result["baseline"]["score_count"], 17)
        self.assertIsNone(result["models"]["S6"]["score"])
        self.assertEqual(result["models"]["S13"]["status"], "REVIEW_REQUIRED")
        self.assertIsNone(result["models"]["PERSONAL_S14_SCENARIO"]["score"])
        self.assertFalse(result["canonical_accepted"])
        self.assertEqual(start, hashlib.sha256(self.baseline_file.read_bytes()).hexdigest())
        db = EvidenceStore(self.root / "personal.db")
        db.save(result)
        self.assertEqual(db.latest("INOD")["receipt_sha256"], result["receipt_sha256"])
        with self.assertRaises(Exception):
            db.save({**result, "canonical_accepted": True})
        paths = export_report(result, self.root / "exports/inod")
        self.assertTrue(all(p.is_file() for p in paths))
        self.assertIn("S13", paths[1].read_text(encoding="utf-8-sig"))

    def test_sec_source_requires_real_exact_body_excerpt_and_sha(self):
        raw = b"<!doctype html><p>Receivables: 5000 USD</p>"
        source = self.root / "original.htm"
        source.write_bytes(raw)
        row = {
            "ticker": "INOD", "cik": "903651", "metric": "receivables",
            "period_end": "2025-12-31", "period_kind": "INSTANT",
            "accession": "0001104659-26-020655", "form_type": "10-K",
            "source_ref": "https://www.sec.gov/Archives/edgar/data/903651/000110465926020655/inod-20251231x10k.htm",
            "source_locator": "to be checked", "source_excerpt": "Receivables: 5000 USD",
            "local_body": source.name, "source_sha256": hashlib.sha256(raw).hexdigest(),
            "accepted_at": "2026-02-26T12:00:00Z",
            "captured_at": "2026-10-12T05:00:00Z", "unit": "USD",
            "value": 5000, "evidence_class": "SOURCE_EXACT",
        }
        packet_path = self.root / "packet.json"
        packet_path.write_text(json.dumps({
            "ticker": "INOD", "cik": "903651", "rows": [row]}), encoding="utf-8")
        data = load_evidence_packet(packet_path)
        kept, rejected = verify_source_rows(data)
        self.assertEqual(len(kept), 1, rejected)
        self.assertEqual(kept[0]["source_locator"], "byte:18")
        source.write_bytes(raw.replace(b"5000", b"9000"))
        kept, rejected = verify_source_rows(data)
        self.assertFalse(kept)
        self.assertIn("SOURCE_BODY_SHA_MISMATCH", rejected[0]["reason"])

    def test_malformed_source_cannot_supply_a_fake_s6_score(self):
        data = {"ticker": "INOD", "cik": "903651",
                "period_end": "2025-12-31", "rows": [{
                    "ticker": "INOD", "metric": "inventory", "value": 0,
                    "evidence_class": "SOURCE_EXACT",
                    "source_sha256": "0" * 64, "source_locator": "invented",
                }]}
        path = self.root / "data.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        result = analyze("INOD", evidence_root=self.root, packet_path=path)
        self.assertIsNone(result["models"]["S6"]["score"])
        self.assertEqual(result["input_count"], 0)
        self.assertTrue(result["rejected_sources"])

    def test_original_s14_zero_s11_is_preserved(self):
        scores = {"S6": {"score": 65}, "B_Q": {"score": 72},
                  "S13": {"score": 40}}
        outcome = assess_personal_s14(scores, s7=100, s11=0, s12=91.528866)
        frozen, components = s14({"S6": 65, "B_Q": 72, "S13": 40,
                                   "S7": 100, "S11": 0, "S12": 91.528866})
        self.assertAlmostEqual(outcome["score"], frozen)
        self.assertEqual(components, outcome["components"]["geometric"])
        self.assertTrue(outcome["components"]["original_zero_s11_preserved"])
        self.assertFalse(outcome["canonical_accepted"])
        self.assertIsNone(assess_personal_s14(
            {"S6": {"score": 50}}, s7=100, s11=0, s12=91)["score"])

    def test_s6_calls_frozen_source_and_keeps_reviewer_gate(self):
        res = assess_s6([], datetime(2026, 10, 12, tzinfo=timezone.utc),
                        source_rsst=0.059140128066)
        self.assertIsNone(res["score"])
        self.assertEqual(res["components"]["diagnostic_rsst"], 0.059140128066)
        self.assertEqual(res["numeric_result_type"], "UNQUANTIFIABLE")

    def test_source_hash_change_changes_verifiable_receipt(self):
        data = {"ticker": "INOD", "cik": "903651"}
        h1 = digest(data)
        data["comment"] = "Accounting restatement evidence required"
        self.assertNotEqual(h1, digest(data))
        with self.assertRaises(ValueError):
            EvidenceStore(self.root / "sidecar.db").save({
                "canonical_accepted": False, "receipt_sha256": "0" * 64})


if __name__ == "__main__":
    unittest.main()
