from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.recovered_quality import SOURCE_SHA256
from app.scoring_v12_core_audit import NAMES, VERSIONS, S1_FORMULAS, _partial_source_rows, audit_report
from scripts.scoring_v12_core_audit import _bytes, _seal, _verify


def _receipt(tmp_path: Path) -> Path:
    models = []
    for name in NAMES:
        models.append({"model": name, "version": VERSIONS[name], "score": None,
                       "missing": ["missing source"], "evidence": {
                           "result": {"score": None, "route_gate": False, "components": {}},
                           "normalized_input_keys": []}})
    report = {"contract_sha256": SOURCE_SHA256, "source_sha256": "a" * 64,
              "stocks": [{"ticker": "REAL", "as_of": "2026-01-01T00:00:00+00:00",
                          "models": models, "control_chain": {"discovery_inputs_present": 5,
                                                                "control_inputs_present": 2}}]}
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    return path


class CoreAuditTests(unittest.TestCase):
    def test_partial_receipt_cannot_promote(self) -> None:
        with TemporaryDirectory() as tmp:
            audit = audit_report(_receipt(Path(tmp)))
        self.assertEqual(audit["accepted_count"], 0)
        self.assertEqual(len(audit["stocks"][0]["models"]), 6)
        s1 = audit["stocks"][0]["models"]["S1"]
        self.assertFalse(s1["gates"]["Core48_exact_inputs"])
        self.assertIn("PIT_feature_provenance", s1["unmet_acceptance"])

    def test_source_mismatch_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            path = _receipt(Path(tmp))
            report = json.loads(path.read_text())
            report["contract_sha256"] = "0" * 64
            path.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, "SHA mismatch"):
                audit_report(path)

    def test_version_mismatch_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            path = _receipt(Path(tmp))
            report = json.loads(path.read_text())
            report["stocks"][0]["models"][0]["version"] = "wrong"
            path.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, "version mismatch"):
                audit_report(path)

    def test_independent_formula_reference(self) -> None:
        c = {"DNA60": 80, "ROUTER_R": 60, "H": 70, "N61": 20,
             "G6": 50, "FPR": 10}
        self.assertAlmostEqual(S1_FORMULAS["S1"](c), 70)
        self.assertAlmostEqual(S1_FORMULAS["S2"](c), 67)
        self.assertAlmostEqual(S1_FORMULAS["S3"](c), 73)

    def test_research_leg_rejects_future_availability(self) -> None:
        row = {"D01_REVENUE_GROWTH_1Y_LEG": {
            "value": 30, "as_of": "2025-01-01T00:00:00+00:00",
            "available_at": "2025-01-02T00:00:00+00:00",
            "source_ref": "https://data.sec.gov/example",
            "evidence_hash": "a" * 64,
        }}
        self.assertFalse(_partial_source_rows(row)["D01_REVENUE_GROWTH_1Y_LEG"]["dated"])

    def test_exact_byte_and_sidecar_verification_is_read_only(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            expected, _ = _bytes(_receipt(root))
            out = root / "audit.json"
            out.write_bytes(expected)
            _seal(out, expected)
            before = (out.read_bytes(), (root / "audit.json.sha256").read_bytes())
            _verify(out, expected)
            self.assertEqual(before, (out.read_bytes(), (root / "audit.json.sha256").read_bytes()))
            out.write_bytes(expected + b" ")
            with self.assertRaisesRegex(ValueError, "saved audit bytes"):
                _verify(out, expected)
            out.write_bytes(expected)
            (root / "audit.json.sha256").write_text("0" * 64 + "\n")
            with self.assertRaisesRegex(ValueError, "sidecar mismatch"):
                _verify(out, expected)


if __name__ == "__main__":
    unittest.main()
