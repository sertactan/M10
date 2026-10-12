import unittest

from app.scoring_v14_s15_readiness import original_gate


class GateTests(unittest.TestCase):
    def test_route_gate_and_confidence_cannot_be_skipped(self):
        result = {"components": {"S15.2": 70, "M10": 71, "T10": 72,
                                 "ROUTE_ESSENTIAL_COVERAGE": 80, "S15.3": 75},
                  "route_gate": False, "confidence": None}
        gate = original_gate(result)
        self.assertFalse(gate["ready"])
        self.assertEqual(gate["missing"], ["ROUTE_GATE", "CONFIDENCE"])

    def test_complete_gate_is_distinct_from_engine_score(self):
        result = {"components": {"S15.2": 70, "M10": 71, "T10": 72,
                                 "ROUTE_ESSENTIAL_COVERAGE": 80, "S15.3": 75},
                  "route_gate": True, "confidence": 74}
        self.assertTrue(original_gate(result)["ready"])
        result["components"]["T10"] = None
        self.assertEqual(original_gate(result)["missing"], ["T10"])


if __name__ == "__main__":
    unittest.main()
