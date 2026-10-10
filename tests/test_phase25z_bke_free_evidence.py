"""Synthetic event/probe checks; no network or private database access."""
import json
import unittest

from scripts.phase25z_bke_free_evidence import build, summarize_nasdaq_response


class BKEFreeEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.w = {"schema": "MERIDYEN_PHASE25W_RESEARCH_PILOT_FAIL_CLOSED_V1",
                  "research_only_pilot_selected": 25, "conflict_rows": 464,
                  "conflict_rows_canonically_resolved": 0, "canonical_accepted_securities_proven": 0,
                  "pilot_candidates": [{"ticker": "BKE", "simfin_id": "196385"}]}
        self.x = {"schema": "phase25x_research_evidence_matrix_v1",
                  "canonical_accepted_securities_proven": 0, "wf9_status": "BLOCKED",
                  "candidates": [{"ticker": "BKE", "overall": "BLOCKED"}]}
        self.y = {"schema": "phase25y_bke_provider_feasibility_v1", "ticker": "BKE",
                  "canonical_accepted_securities_proven": 0, "wf9_status": "BLOCKED"}

    def test_event_leads_do_not_admit_canonical(self):
        result = build(self.w, self.x, self.y, None)
        self.assertEqual(result["event_count"], 8)
        self.assertEqual(result["specific_ex_dates_verified"], 0)
        self.assertTrue(all(r["ex_date"] is None for r in result["official_event_leads"]))
        self.assertEqual(result["canonical_accepted_security_dates"], 0)
        self.assertEqual(result["canonical_gates"]["independent_adjusted_price"], "BLOCKED")

    def test_nasdaq_raw_close_is_not_adjusted_proof(self):
        response = {"status": {"rCode": 200}, "data": {"symbol": "BKE",
                    "tradesTable": {"rows": [{"date": "01/15/2025", "close": "$48.35",
                                               "open": "$47.00", "volume": "100"}]}}}
        result = summarize_nasdaq_response(json.dumps(response).encode(), "2024-01-01", "2025-09-30")
        self.assertEqual(result["row_count"], 1)
        self.assertFalse(result["has_adjusted_close_field"])
        self.assertEqual(result["private_price_samples"][0]["source_close"], "$48.35")

    def test_response_outside_requested_dates_rejected(self):
        response = {"status": {"rCode": 200}, "data": {"symbol": "BKE",
                    "tradesTable": {"rows": [{"date": "01/15/2023", "close": "$40"}]}}}
        with self.assertRaisesRegex(ValueError, "outside requested range"):
            summarize_nasdaq_response(json.dumps(response).encode(), "2024-01-01", "2025-09-30")

    def test_wrong_symbol_rejected(self):
        response = {"status": {"rCode": 200}, "data": {"symbol": "OTHER", "tradesTable": {"rows": []}}}
        with self.assertRaisesRegex(ValueError, "symbol mismatch"):
            summarize_nasdaq_response(json.dumps(response).encode(), "2024-01-01", "2025-09-30")

    def test_prior_canonical_change_rejected(self):
        self.x["canonical_accepted_securities_proven"] = 1
        with self.assertRaisesRegex(ValueError, "Phase25X"):
            build(self.w, self.x, self.y, None)


if __name__ == "__main__":
    unittest.main()
