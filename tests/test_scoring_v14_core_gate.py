from __future__ import annotations

from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from app.scoring_v14_core_gate import _offline_counts, build_gate_receipt, original_inventory


def _contract() -> bytes:
    d = "\n".join(f"{i}. Discovery {i}" for i in range(1,49))
    c = "\n".join(f"{i}. Control {i}" for i in range(49,61))
    return ("# 1. 48 TEMEL\n"+d+"\n# 2. 48 DISCOVERY\n"
            "# 4. FAKTÖR 49\n"+c+"\n## 4.1\n").encode()


def _sealed(path: Path, data: dict) -> None:
    raw = json.dumps(data).encode()
    path.write_bytes(raw)
    path.with_name(path.name+".sha256").write_text(sha256(raw).hexdigest()+"\n")


class CoreGateTests(unittest.TestCase):
    def test_exact_48_and_12_inventory(self) -> None:
        source = _contract()
        with patch("app.scoring_v14_core_gate.FROZEN_SOURCE_SHA256", sha256(source).hexdigest()):
            inventory = original_inventory(source)
        self.assertEqual(len(inventory["discovery"]), 48)
        self.assertEqual(len(inventory["control"]), 12)

    def test_offline_history_and_factor_keys(self) -> None:
        with TemporaryDirectory() as temp:
            path = Path(temp)/"backup.db"
            with closing(sqlite3.connect(path)) as db:
                db.execute("create table s153_historical_control_observations(id integer)")
                db.execute("create table canonical_model_features(feature_key text)")
                db.execute("insert into canonical_model_features values ('RAW_CURRENT_PRICE')")
                db.commit()
            counts = _offline_counts(path)
        self.assertEqual(counts["historical_observations"], 0)
        self.assertEqual(counts["canonical_D_F_keys"], [])
        self.assertEqual(counts["read_mode"], "SQLITE_MODE_RO_QUERY_ONLY")

    def test_missing_original_operands_never_promoted(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            source = _contract()
            contract = root/"contract.md"
            contract.write_bytes(source)
            report = root/"report.json"
            models = [{"model": n, "score": None} for n in ("S1","S2","S3")]
            _sealed(report, {"contract_sha256": sha256(source).hexdigest(),
                             "stocks": [{"ticker": "ONE", "as_of": "2025-01-01",
                                         "models": models, "control_chain": {
                                             "discovery_inputs_present": 3,
                                             "control_inputs_present": 1,
                                             "historical_h": None,
                                             "n61": None,
                                             "false_positive_risk": None}}]})
            factors = root/"factors.json"
            _sealed(factors, {"frozen_contract_sha256": sha256(source).hexdigest(),
                              "normalized_quality_scores": {"F52_RPS": None,"F53_FPS": None},
                              "submissions_sha256": "a" * 64,
                              "raw_factor_formulas_verified": ["F52_RPSGrowth_1Y", "F53_FPSGrowth_1Y"]})
            db = root/"backup.db"
            with closing(sqlite3.connect(db)) as con:
                con.execute("create table s153_historical_control_observations(id integer)")
                con.execute("create table canonical_model_features(feature_key text)")
                con.commit()
            with patch("app.scoring_v14_core_gate.FROZEN_SOURCE_SHA256", sha256(source).hexdigest()):
                result = build_gate_receipt(contract=contract, v12_report=report,
                                            v13_raw_factors=factors, offline_db=db)
                legs = ["D01_REVENUE_GROWTH_1Y_LEG", "D02_EPS_GROWTH_1Y_LEG",
                        "D03_REVENUE_ACCELERATION_LEG", "F54_DIL_RESEARCH_LEG"]
                binding = root/"binding.json"
                binding_data = {"ticker": "INOD", "report_sha256": sha256(report.read_bytes()).hexdigest(),
                                "submissions_sha256": "a" * 64,
                                "evidence_rows_bound": 9, "partial_legs_bound": 4,
                                "canonical_pit_accepted": False, "s1_s2_s3_complete_scores": 0,
                                "evidence": [{"leg": legs[i % 4], "accession": f"accession-{i % 4}",
                                              "form": "10-K", "accepted_at": "2025-01-01T00:00:00Z",
                                              "fact_hash": "c" * 64} for i in range(9)]}
                _sealed(binding, binding_data)
                joined = build_gate_receipt(contract=contract, v12_report=report,
                                            v13_raw_factors=factors, offline_db=db,
                                            v13_sec_binding=binding)
                binding_data["report_sha256"] = "b" * 64
                _sealed(binding, binding_data)
                with self.assertRaisesRegex(ValueError, "binding invalid"):
                    build_gate_receipt(contract=contract, v12_report=report,
                                       v13_raw_factors=factors, offline_db=db,
                                       v13_sec_binding=binding)
        self.assertEqual(result["new_complete_scores"], 0)
        self.assertEqual(result["stocks"][0]["missing"]["discovery_count"], 45)
        self.assertTrue(result["stocks"][0]["missing"]["historical_H"])
        self.assertEqual(joined["inod_original_sec_binding"]["source_rows"], 9)



if __name__ == "__main__":
    unittest.main()
