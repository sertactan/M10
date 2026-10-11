"""Material Task 9/10 guards and authenticated private source replay."""
import os
from pathlib import Path
import unittest

from app.scoring_v12_quality_audit import expert_packet, independent_s14_reference, verified_json


class QualityAuditTests(unittest.TestCase):
    def test_s14_reference_preserves_true_zero_and_missing_gate(self):
        from core.scoring.s1_s14 import s14
        legs = {"B_Q": 60, "S6": 70, "S7": 100, "S11": 0,
                "S12": 91.528866, "S13": 75}
        ref = independent_s14_reference(legs)
        self.assertIsNotNone(ref)
        self.assertAlmostEqual(float(ref), s14(legs)[0], places=10)
        legs["B_Q"] = None
        self.assertIsNone(independent_s14_reference(legs))
        self.assertIsNone(s14(legs)[0])

    def test_source_seal_detects_mutation(self):
        import hashlib
        raw = b'{"x":1}'
        valid = hashlib.sha256(raw).hexdigest().encode()
        self.assertEqual(verified_json(raw, valid), {"x": 1})
        with self.assertRaisesRegex(ValueError, "SOURCE_RECEIPT_SEAL_CHANGED"):
            verified_json(raw + b" ", valid)

    def test_expert_packet_rejects_fake_signoff(self):
        path = Path("E:/M10/.scoring_v5_private/s13/s13_expert_form_v5.json")
        if not path.is_file():
            self.skipTest("Private expert source unavailable")
        import copy, hashlib, json
        raw = path.read_bytes()
        form = verified_json(raw, Path(str(path) + ".sha256").read_bytes())
        packet = expert_packet(form, hashlib.sha256(raw).hexdigest())
        self.assertEqual((packet["source_findings"], packet["signed_blocks"]), (27, 0))
        self.assertIsNone(packet["S13"])
        fake = copy.deepcopy(form)
        fake["blocks"]["AUD"]["signed"] = True
        with self.assertRaisesRegex(ValueError, "S13_REVIEW_STATE_CHANGED"):
            expert_packet(fake, hashlib.sha256(raw).hexdigest())

    def test_private_offline_replay(self):
        if not os.environ.get("LOCALAPPDATA"):
            self.skipTest("Windows private sources unavailable")
        from scripts.scoring_v12_quality_audit import OUTPUT, run
        if not OUTPUT.is_file():
            self.skipTest("Private V12 packet not yet generated")
        result = run(verify=True)
        self.assertEqual(result["status"], "SOURCE_AUDITED_NO_NEW_FULL_SCORE")
        self.assertEqual(result["S13_signed_blocks"], 0)
        self.assertIsNone(result["INOD_S14"])


if __name__ == "__main__":
    unittest.main()
