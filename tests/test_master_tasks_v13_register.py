import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.master_tasks_v13_register import validate_v13

ROOT = Path(__file__).resolve().parents[1]
V12 = ROOT / "docs/MASTER_TASKS_V12_REGISTER.json"
V13 = ROOT / "docs/MASTER_TASKS_V13_REGISTER.json"


class RegisterTests(unittest.TestCase):
    def test_current_record_and_v12_continuity(self):
        result = validate_v13(V13, V12)
        self.assertEqual(result["total_criteria"], 40)
        self.assertEqual(result["done_tasks"], 0)

    def test_cannot_erase_a_v12_pass(self):
        data = json.loads(V13.read_text(encoding="utf-8"))
        data["tasks"][0]["criteria"][0]["verified"] = False
        with TemporaryDirectory() as temp:
            path = Path(temp) / "register.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ValueError):
                validate_v13(path, V12)


if __name__ == "__main__":
    unittest.main()
