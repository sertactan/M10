"""Synthetic fail-closed tests for the offline Phase25Y BKE audit."""
import copy
import unittest

from scripts.phase25y_provider_feasibility import audit, REQUIRED_GATES, W_SCHEMA, X_SCHEMA


def fixtures():
    w = {
        "schema": W_SCHEMA, "research_only_pilot_selected": 25,
        "conflict_rows": 464, "conflict_rows_canonically_resolved": 0,
        "canonical_accepted_securities_proven": 0,
        "pilot_candidates": [{"ticker": "BKE", "simfin_id": "196385"}],
    }
    gates = {gate: "BLOCKED" for gate in REQUIRED_GATES}
    gates["historical_cik_share_class"] = "PARTIAL"
    gates["sec_publication_and_feature_available_at"] = "PARTIAL"
    x = {
        "schema": X_SCHEMA, "phase25w_pilot_count": 25,
        "phase25w_conflict_rows_quarantined": 464,
        "canonical_accepted_securities_proven": 0,
        "canonical_accepted_security_dates_proven": 0,
        "period": {"start": "2024-01-01", "end": "2025-09-30"},
        "candidates": [{
            "ticker": "BKE", "simfin_id": "196385",
            "present_day_cik_candidate": "0000885245",
            "source_price_rows": 438, "source_months": 21,
            "local_period_fact_rows": 318, "local_period_accepted_at_rows": 0,
            "sec_filing_anchor": {"accession": "0000885245-24-000051",
                                  "local_fact_accepted_at_rows": 0},
            "gate_status": gates, "overall": "BLOCKED", "canonical_admitted": False,
        }],
    }
    return w, x


class ProviderFeasibilityTests(unittest.TestCase):
    def test_valid_prior_reports_stay_blocked(self):
        w, x = fixtures()
        result = audit(w, x)
        self.assertEqual(result["canonical_accepted_securities_proven"], 0)
        self.assertEqual(result["wf9_status"], "BLOCKED")
        self.assertFalse(result["provider_data_acquired"])

    def test_canonical_upgrade_rejected(self):
        w, x = fixtures()
        x["canonical_accepted_securities_proven"] = 1
        with self.assertRaises(ValueError):
            audit(w, x)

    def test_quarantine_regression_rejected(self):
        w, x = fixtures()
        w["conflict_rows_canonically_resolved"] = 1
        with self.assertRaises(ValueError):
            audit(w, x)

    def test_missing_gate_rejected(self):
        w, x = fixtures()
        del x["candidates"][0]["gate_status"]["delisting_terminal_payoff"]
        with self.assertRaises(ValueError):
            audit(w, x)

    def test_claimed_gate_pass_rejected(self):
        w, x = fixtures()
        x["candidates"][0]["gate_status"]["independent_adjusted_price"] = "PASS"
        with self.assertRaises(ValueError):
            audit(w, x)


if __name__ == "__main__":
    unittest.main()
