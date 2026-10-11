from __future__ import annotations

import json
import unittest

from app.scoring_v13_estimated_oos import REQUIRED_FACTORS, audit_real_pilot, check_case


def case():
    return {
        "split": "TRAIN", "decision_at": "2024-06-01T15:00:00Z",
        "outcome_end": "2024-06-07T20:00:00Z",
        "label_available_at": "2024-06-08T00:00:00Z",
        "verified_exchange_session_horizon": True,
        "historical_identity_verified": True,
        "corporate_actions_verified": True,
        "delisting_outcome_verified": True,
        "contemporaneous_membership_verified": True,
        "factors": {key: {"source_ref": "https://archive.example/record",
                          "source_sha256": "a" * 64,
                          "availability_basis": "HISTORICAL_PROVIDER_CAPTURE",
                          "first_available_at": "2024-06-01T14:00:00Z"}
                    for key in REQUIRED_FACTORS},
    }


class EstimatedOosTests(unittest.TestCase):
    def test_valid_case_and_future_factor(self):
        row = case()
        self.assertEqual(check_case(row, evaluation_as_of="2024-06-10T00:00:00Z"), [])
        row["factors"][next(iter(REQUIRED_FACTORS))]["first_available_at"] = "2024-06-02T00:00:00Z"
        self.assertTrue(any(reason.endswith(":LOOKAHEAD") for reason in check_case(row, evaluation_as_of="2024-06-10T00:00:00Z")))

    def test_split_crossing_and_unmatured_label(self):
        row = case()
        row["decision_at"] = "2024-12-30T15:00:00Z"
        row["outcome_end"] = "2025-01-03T20:00:00Z"
        row["label_available_at"] = "2025-01-04T00:00:00Z"
        issues = check_case(row, evaluation_as_of="2024-12-31T23:59:59Z")
        self.assertIn("LABEL_CROSSES_NEXT_SPLIT", issues)
        self.assertIn("FUTURE_OR_UNMATURED_LABEL", issues)

    def test_missing_ten_factors_blocks_and_naive_time_fails(self):
        row = case()
        row["factors"] = {}
        self.assertIn("TEN_REQUIRED_FACTORS_MISSING", check_case(row, evaluation_as_of="2024-06-10T00:00:00Z"))
        row = case()
        row["decision_at"] = "2024-06-01T15:00:00"
        self.assertEqual(check_case(row, evaluation_as_of="2024-06-10T00:00:00Z"), ["CASE_CLOCKS_MISSING_OR_INVALID"])

    def test_real_pilot_shape_gives_no_metrics(self):
        candidates = [{"simfin_id": str(i), "first_source_price_date": "2024-01-02",
                       "last_source_price_date": "2025-09-30", "source_price_rows": 438}
                      for i in range(25)]
        source = {"schema": "RESEARCH_ONLY", "canonical_accepted_securities_proven": 0,
                  "pilot_candidates": candidates,
                  "remaining_global_blockers": ["RETROSPECTIVE_MEMBERSHIP"]}
        result = audit_real_pilot(json.dumps(source).encode(), evaluation_as_of="2026-10-12T00:00:00Z")
        self.assertEqual(result["pilot_security_count"], 25)
        self.assertEqual(result["eligible_oos_cases"], 0)
        self.assertIsNone(result["metrics"])
        self.assertFalse(result["runtime_enabled"])


if __name__ == "__main__":
    unittest.main()
