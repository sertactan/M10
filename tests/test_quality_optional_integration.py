"""Synthetic packets confirm recovered quality legs plug into frozen S14 inputs."""
import unittest

from app.recovered_quality import compute_quality
from tests.test_recovered_beneish import AT, two_years
from tests.test_recovered_dechow import fixture as dechow_fixture, reviews as dechow_reviews
from tests.test_recovered_jones import target, peers
from tests.test_forensic_evidence import fixture as forensic_fixture


class IntegratedQualityTests(unittest.TestCase):
    def test_unprovided_packets_never_generate_s6_s11_s13(self):
        q=compute_quality(two_years(),AT)
        self.assertIsNone(q["S6"]["score"])
        self.assertIsNone(q["S11"]["score"])
        self.assertIsNone(q["S13"]["score"])

    def test_synthetic_s6_s11_s13_under_explicit_verified_evidence(self):
        sample=compute_quality(two_years(),AT,
            dechow_packet={"periods":dechow_fixture(), **dechow_reviews()},
            jones_packet={"target":target(), "peers":peers()},
            forensic_packet=forensic_fixture())
        self.assertEqual(sample["S6"]["score"],95)
        self.assertGreater(sample["S11"]["score"],0)
        self.assertEqual(sample["S13"]["score"],100)
        for model in ("S6","S11","S13"):
            with self.subTest(model=model):
                self.assertEqual(sample[model]["status"],"VERIFIED_DONE")
                self.assertFalse(sample[model]["canonical_accepted"])
                self.assertEqual(sample[model]["scope"],"RESEARCH_ONLY_NOT_CANONICAL_PIT")
                self.assertEqual(len(sample[model]["evidence_hash"]),64)
                self.assertEqual(sample[model]["evidence"]["contract_sha256"],
                    "53dce841fd5ebdfeb00636f327493be1255ea8b60e6df4eadd921a7098813794")

    def test_missing_forensic_reviews_do_not_become_zero_flags(self):
        q=compute_quality(two_years(),AT,forensic_packet={})
        self.assertIsNone(q["S13"]["score"])
        self.assertIsNone(q["B_Q"]["score"])
        self.assertIn("INDEPENDENT_SERIOUS_FLAGS_REVIEW_COMPLETE",q["B_Q"]["missing"])


if __name__=="__main__":
    unittest.main()
