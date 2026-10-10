from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import phase26b_seed_gate as gate
from scripts.phase26b_full_backup import collect_app_state


class Phase26BSeedGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.seed = self.root / "public"
        self.seed.mkdir()
        self.notices = self.root / "notices.md"
        self.notices.write_text("MIT notice", encoding="utf-8")
        with patch.dict(gate.EXPECTED, {
            "sec_us_current.csv": ("transport", {"SEC_DIRECT"}, 1),
            "jp_tr_hk_current.csv": ("source", {"FINANCEDATABASE_MIT_REFERENCE"}, 1),
        }, clear=True):
            self._write("sec_us_current.csv", "transport", "SEC_DIRECT")
            self._write("jp_tr_hk_current.csv", "source", "FINANCEDATABASE_MIT_REFERENCE")
        self.small = patch.dict(gate.EXPECTED, {
            "sec_us_current.csv": ("transport", {"SEC_DIRECT"}, 1),
            "jp_tr_hk_current.csv": ("source", {"FINANCEDATABASE_MIT_REFERENCE"}, 1),
        }, clear=True)
        self.small.start()
        self.addCleanup(self.small.stop)

    def _write(self, name: str, field: str, value: str) -> None:
        with (self.seed / name).open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=[field, "ticker"])
            writer.writeheader()
            writer.writerow({field: value, "ticker": "TEST"})

    def test_clean_seed_is_private_test_only_without_external_approval(self) -> None:
        gate.prepare_test_manifest(self.seed, self.notices)
        gate.verify(self.seed, self.notices, private_test=True)
        with self.assertRaisesRegex(ValueError, "External distribution approval"):
            gate.verify(self.seed, self.notices, private_test=False)

    def test_private_db_export_and_tamper_are_rejected(self) -> None:
        gate.prepare_test_manifest(self.seed, self.notices)
        self._write("sec_us_current.csv", "transport", "LOCAL_DB_EXPORT_SMOKE_ONLY")
        with self.assertRaisesRegex(ValueError, "Unapproved"):
            gate.verify(self.seed, self.notices, private_test=True)

    def test_release_approval_must_match_hashes(self) -> None:
        manifest = gate.prepare_test_manifest(self.seed, self.notices)
        approval = self.root / "approval.json"
        approval.write_text(json.dumps({"status": "APPROVED_FOR_DISTRIBUTION",
                                        "approver": "owner", "license_review_reference": "review",
                                        "seed_sha256": {"sec_us_current.csv": "wrong"}}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "does not match"):
            gate.verify(self.seed, self.notices, private_test=False, approval=approval)
        self.assertEqual(manifest["status"], "PRIVATE_TEST_ONLY")


class Phase26BBackupScopeTests(unittest.TestCase):
    def test_prior_backup_and_new_backup_are_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("runtime", "logs", "backups", "runtime/phase26a", "runtime/phase26b"):
                (root / name).mkdir(parents=True, exist_ok=True)
            (root / "settings.json").write_text("{}", encoding="utf-8")
            (root / "runtime/data.txt").write_text("data", encoding="utf-8")
            (root / "runtime/phase26a/old.txt").write_text("old", encoding="utf-8")
            (root / "runtime/phase26b/new.txt").write_text("new", encoding="utf-8")
            price = root / "price.csv"
            price.write_text("price", encoding="utf-8")
            files = collect_app_state(root, price)
            self.assertIn("app_state/runtime/data.txt", files)
            self.assertIn("app_state/settings.json", files)
            self.assertNotIn("app_state/runtime/phase26a/old.txt", files)
            self.assertNotIn("app_state/runtime/phase26b/new.txt", files)


if __name__ == "__main__":
    unittest.main()