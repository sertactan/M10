"""Synthetic research sensitivity and fail-closed tests."""
import sqlite3
from contextlib import closing
import unittest

from scripts.phase25y_research_only_backtest import equal_weight_path, months
from scripts.phase25z_research_backtest_v2 import diagnostics, evaluate, percentile


class Phase25ZV2Tests(unittest.TestCase):
    def make_series(self):
        keys = months()
        series = {f"T{i:02d}": {m: {"trade_date": m + "-28", "adj_close": 1.0,
                                      "close": 1.0} for m in keys} for i in range(25)}
        series["T00"][keys[-1]]["adj_close"] = 2.0
        dates = {t: {v["trade_date"] for v in rows.values()} for t, rows in series.items()}
        return series, dates

    def test_loo_and_exact_contributions_tie_to_baseline(self):
        series, dates = self.make_series()
        baseline = equal_weight_path(series)
        result = diagnostics(series, dates, baseline)
        self.assertEqual(result["source_adj_index_final"], 1.04)
        self.assertEqual(result["monthly_diagnostics"][-1]["source_close_index"], 1.0)
        self.assertAlmostEqual(result["contribution_sum"], 0.04)
        self.assertEqual(result["leave_one_out"]["T00"]["index_without"], 1.0)
        self.assertEqual(result["most_influential_leave_one_out"][0], "T00")
        self.assertEqual(result["median_index_final"], 1.0)
        self.assertLess(result["winsor_5_95_index_final"], 1.04)
        self.assertEqual(result["stock_concentration"]["top_one_abs_contribution_share"], 1.0)
        self.assertIsNone(result["historical_sector_concentration"])

    def test_missing_source_date_is_measured_against_union(self):
        series, dates = self.make_series()
        dates["T01"].remove("2024-01-28")
        result = diagnostics(series, dates, equal_weight_path(series))
        self.assertEqual(result["missing_dates_against_source_union"]["T01"], 1)
        self.assertFalse(result["source_calendar_certified"])

    def test_baseline_disagreement_rejected(self):
        series, dates = self.make_series()
        baseline = equal_weight_path(series)
        baseline["source_adj_index_final"] = 9.0
        with self.assertRaisesRegex(ValueError, "does not reproduce"):
            diagnostics(series, dates, baseline)

    def test_percentile_linear_interpolation(self):
        self.assertAlmostEqual(percentile([0, 1, 2, 3, 4], 0.05), 0.2)
        self.assertAlmostEqual(percentile([0, 1, 2, 3, 4], 0.95), 3.8)

    def test_canonical_change_rejected_before_source_query(self):
        w = {"schema": "MERIDYEN_PHASE25W_RESEARCH_PILOT_FAIL_CLOSED_V1",
             "research_only_pilot_selected": 25, "pilot_candidates": [{} for _ in range(25)],
             "conflict_rows": 464, "conflict_quarantine_rows": [{} for _ in range(464)],
             "conflict_rows_canonically_resolved": 0, "canonical_accepted_securities_proven": 1}
        with closing(sqlite3.connect(":memory:")) as db:
            with self.assertRaisesRegex(ValueError, "Phase25W"):
                evaluate(w, {}, {}, {}, db)


if __name__ == "__main__":
    unittest.main()
