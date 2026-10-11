from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from app.master_tasks_v12_register import validate_register


SOURCE = Path(__file__).resolve().parents[1] / "docs/MASTER_TASKS_V12_REGISTER.json"


class MasterTaskRegisterTests(unittest.TestCase):
    def test_real_register_counts_only_evidenced_criteria(self):
        result = validate_register(SOURCE)
        self.assertEqual(result["done_tasks"], 0)
        self.assertEqual(result["baseline_verified_criteria"], 10)
        self.assertEqual(result["verified_criteria"], 13)

    def test_done_cannot_be_declared_with_missing_gate(self):
        data = json.loads(SOURCE.read_text(encoding="utf-8"))
        data["tasks"][0]["status"] = "DONE"
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "register.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "DONE_REQUIRES_ALL"):
                validate_register(path)

    def test_verified_gate_requires_test_and_evidence(self):
        data = json.loads(SOURCE.read_text(encoding="utf-8"))
        data["tasks"][0]["criteria"][1]["verified"] = True
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "register.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "NEEDS_EVIDENCE"):
                validate_register(path)


if __name__ == "__main__":
    unittest.main()
