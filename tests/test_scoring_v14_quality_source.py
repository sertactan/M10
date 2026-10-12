"""Original-source and non-promotion checks for the V14 INOD quality census."""
import json
from pathlib import Path
import unittest

from app.scoring_v14_quality_source import audit_quality_sources
from scripts.scoring_v13_quality_ixbrl import BODIES
from scripts.scoring_v14_quality_audit import V12, V13, run


class QualitySourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not all(p.is_file() for p in (*BODIES, V12, V13)):
            raise unittest.SkipTest("Private original SEC and quality receipts unavailable")
        cls.filings = list(zip((p.read_bytes() for p in BODIES),
                               json.loads(V13.read_bytes())["filings"]))
        cls.v12 = json.loads(V12.read_bytes())

    def test_exact_original_fact_census_preserves_missing(self):
        result = audit_quality_sources(self.filings, self.v12)
        by_accession = {r["accession"]: r for r in result["filings"]}
        current = by_accession["0001104659-26-020655"]
        prior = by_accession["0001410578-25-000194"]
        self.assertEqual((current["ix_nonfraction_rows"], prior["ix_nonfraction_rows"]), (898, 902))
        self.assertEqual(len(prior["short_term_investment_candidates"]), 2)
        self.assertEqual(current["short_term_investment_balance_names"], [])
        for row in (current, prior):
            self.assertEqual(row["inventory_names"], [])
            self.assertEqual(row["pure_depreciation_names"], [])
            self.assertEqual(row["preferred_value_nil_rows"], 2)
            self.assertFalse(row["missing_tag_inferred_zero"])
        self.assertEqual((result["S6_verified_inputs"], result["B_Q_verified_risks"]), (5, 5))
        self.assertEqual(result["S13_signed_blocks"], 0)
        self.assertTrue(all(result[k] is None for k in ("S6", "B_Q", "S13", "S14")))

    def test_filing_mutation_rejected(self):
        changed = self.filings.copy()
        changed[0] = (changed[0][0] + b" ", changed[0][1])
        with self.assertRaisesRegex(ValueError, "ORIGINAL_FILING_OR_PRIOR_RECEIPT_CHANGED"):
            audit_quality_sources(changed, self.v12)

    def test_unsigned_expert_packet_cannot_be_promoted(self):
        changed = json.loads(json.dumps(self.v12))
        changed["S13"]["blocks"]["AUD"]["signed"] = True
        with self.assertRaisesRegex(ValueError, "V12_S13_S14_ACCEPTANCE_STATE_CHANGED"):
            audit_quality_sources(self.filings, changed)

    def test_private_offline_replay(self):
        result = run(verify=True)
        self.assertEqual(result["filing_fact_counts"], [898, 902])
        self.assertEqual((result["task9"], result["task10"]), ("PARTIAL", "BLOCKED"))


if __name__ == "__main__":
    unittest.main()
