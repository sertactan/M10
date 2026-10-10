"""Synthetic guardrails and arithmetic tests only; no user data opened."""
import sqlite3
import unittest

from scripts.phase25y_research_only_backtest import (
    equal_weight_path, evaluate, month_end_series, months,
)


class Phase25YResearchBacktestTests(unittest.TestCase):
    def test_known_monthly_equal_weight_path(self):
        month_keys = months()
        flat = {m: {"trade_date": m + "-28", "adj_close": 1.0, "close": 1.0} for m in month_keys}
        jump = {m: dict(row) for m, row in flat.items()}
        jump[month_keys[-1]] = {"trade_date": month_keys[-1] + "-28", "adj_close": 2.0, "close": 1.5}
        result = equal_weight_path({"A": flat, "B": jump})
        self.assertEqual(result["interval_count"], 20)
        self.assertEqual(result["source_adj_index_final"], 1.5)
        self.assertEqual(result["source_close_index_final"], 1.25)

    def test_month_end_selects_last_observed_row(self):
        bars = [(m + "-01", 1.0, 1.0) for m in months()]
        bars.append(("2024-01-31", 2.0, 2.0))
        result = month_end_series(bars, len(bars))
        self.assertEqual(result["2024-01"]["trade_date"], "2024-01-31")

    def test_missing_month_is_rejected(self):
        bars = [(m + "-01", 1.0, 1.0) for m in months()[:-1]]
        with self.assertRaisesRegex(ValueError, "missing monthly"):
            month_end_series(bars, len(bars))

    def test_positive_price_required(self):
        bars = [(m + "-01", 1.0, 1.0) for m in months()]
        bars[-1] = (bars[-1][0], 0.0, 1.0)
        with self.assertRaisesRegex(ValueError, "invalid source price"):
            month_end_series(bars, len(bars))

    def test_nonzero_canonical_baseline_rejected_before_price_query(self):
        w = {"schema": "MERIDYEN_PHASE25W_RESEARCH_PILOT_FAIL_CLOSED_V1",
             "research_only_pilot_selected": 25, "pilot_candidates": [{} for _ in range(25)],
             "conflict_rows": 464, "conflict_rows_canonically_resolved": 0,
             "conflict_quarantine_rows": [{} for _ in range(464)],
             "canonical_accepted_securities_proven": 1}
        with sqlite3.connect(":memory:") as db:
            with self.assertRaisesRegex(ValueError, "Phase25W"):
                evaluate(w, {}, {}, db)


if __name__ == "__main__":
    unittest.main()
