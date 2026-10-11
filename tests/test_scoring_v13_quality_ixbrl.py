"""Real original-filing iXBRL receipt and missing-value acceptance guards."""
import json
from pathlib import Path
import tempfile
import unittest

from app.scoring_v13_quality_ixbrl import _monetary_candidate, inspect_filing
from scripts.scoring_v13_quality_ixbrl import BODIES, run


class QualityIxbrlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if any(not path.is_file() for path in BODIES):
            raise unittest.SkipTest("Private original INOD SEC bodies unavailable")

    def test_original_2024_comparative_sti_candidate_and_no_zero_inference(self):
        now = inspect_filing(BODIES[0], Path(str(BODIES[0]) + ".receipt.json"))
        prior = inspect_filing(BODIES[1], Path(str(BODIES[1]) + ".receipt.json"))
        self.assertEqual(now["short_term_investment_monetary_candidates"], [])
        self.assertEqual({(r["period_end"], r["value_usd"]) for r in
                          prior["short_term_investment_monetary_candidates"]},
                         {("2023-12-31", "14000"), ("2024-12-31", "14000")})
        self.assertTrue(now["inventory_tag_absent"])
        self.assertFalse(now["inventory_value_inferred_zero"])
        self.assertFalse(prior["accounting_classification_accepted"])

    def test_nil_and_lexical_none_cannot_become_zero(self):
        row = {"name": "us-gaap:OtherShortTermInvestments", "nil": "true",
               "unit": "Unit_Standard_USD_x", "text": "0", "scale": "0",
               "context": "As_Of_12_31_2024_a", "sign": None}
        self.assertIsNone(_monetary_candidate(row))
        row["nil"] = None
        row["text"] = "none"
        self.assertIsNone(_monetary_candidate(row))

    def test_changed_body_and_receipt_are_rejected(self):
        path = BODIES[0]
        with tempfile.TemporaryDirectory() as d:
            body = Path(d) / path.name
            receipt = Path(str(body) + ".receipt.json")
            body.write_bytes(path.read_bytes() + b" ")
            receipt.write_bytes(Path(str(path) + ".receipt.json").read_bytes())
            with self.assertRaisesRegex(ValueError, "original filing body seal mismatch"):
                inspect_filing(body, receipt)
            body.write_bytes(path.read_bytes())
            data = json.loads(receipt.read_bytes())
            data["accession"] = "0001410578-25-000194"
            receipt.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "wrong filing identity"):
                inspect_filing(body, receipt)

    def test_private_offline_replay(self):
        result = run(verify=True)
        self.assertEqual(result["short_term_investment_candidate_rows"], 2)
        self.assertIsNone(result["new_S6_score"])
        self.assertIsNone(result["INOD_S14"])


if __name__ == "__main__":
    unittest.main()
