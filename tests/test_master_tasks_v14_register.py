import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.master_tasks_v14_register import validate_v14

ROOT = Path(__file__).resolve().parents[1]
V13 = ROOT / "docs/MASTER_TASKS_V13_REGISTER.json"
V14 = ROOT / "docs/MASTER_TASKS_V14_REGISTER.json"


class RegisterTests(unittest.TestCase):
    def test_current_record(self):
        result = validate_v14(V14, V13)
        self.assertEqual(result["total_criteria"], 40)

    def test_v13_verified_gate_cannot_regress(self):
        data = json.loads(V14.read_text(encoding="utf-8"))
        next(c for t in data["tasks"] for c in t["criteria"]
             if c["id"] == "18.build")["verified"] = False
        with TemporaryDirectory() as temp:
            path = Path(temp) / "register.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ValueError):
                validate_v14(path, V13)

    def test_audit_cannot_claim_unverified_gate(self):
        data = json.loads(V14.read_text(encoding="utf-8"))
        gate = next(c for t in data["tasks"] for c in t["criteria"]
                    if c["id"] == "18.deployment")
        gate["v14_audit"]["decision"] = "VERIFIED"
        with TemporaryDirectory() as temp:
            path = Path(temp) / "register.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "V14_AUDIT_DECISION_MISMATCH"):
                validate_v14(path, V13)


if __name__ == "__main__":
    unittest.main()
