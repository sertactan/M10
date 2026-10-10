"""Synthetic contract tests only: no genuine score or calibration evidence."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from app.scoring_estimated_draft import (
    ACTIVATION_STATUS, FACTORS, RISKS, Evidence, ReplayCase, experiment, evaluate_frozen_replay,
)

NOW = datetime(2026, 10, 9, 20, tzinfo=timezone.utc)


def inputs():
    result = {}
    for spec in FACTORS + RISKS:
        value = (spec.low+spec.high)/2
        end = NOW-timedelta(hours=value if spec.key == "catalyst_age_hours" else .5)
        result[spec.key] = Evidence(value, spec.unit, end, end, end,
                                   "https://fixtures.invalid/synthetic", "ab"*32,
                                   "PROVIDER_CAPTURE_LOG", True)
    return result


def run(data=None):
    return experiment(inputs() if data is None else data, as_of=NOW,
                      acknowledge_unapproved_experiment=True)


class EstimatedDraftTests(unittest.TestCase):
    def test_explicit_experiment_only_no_activation(self):
        untouched = experiment(inputs(), as_of=NOW)
        self.assertIsNone(untouched["experimental_score"])
        result = run()
        self.assertFalse(result["canonical"])
        self.assertFalse(result["runtime_enabled"])
        self.assertEqual(result["activation_status"], "PENDING_APPROVAL")
        self.assertEqual(ACTIVATION_STATUS, "PENDING_APPROVAL")
        self.assertEqual(result["confidence"], "UNCALIBRATED")

    def test_independent_reference_and_determinism(self):
        # All seven factor midpoints = 50; each of three penalties = 7.5.
        data = inputs()
        self.assertAlmostEqual(sum(s.weight for s in FACTORS), 1)
        self.assertEqual(run(data)["experimental_score"], 27.5)
        self.assertEqual(run(data), run(dict(reversed(list(data.items())))))
        self.assertEqual(data, inputs())

    def test_each_required_input_blocks_and_no_weight_renormalization(self):
        for spec in FACTORS + RISKS:
            with self.subTest(key=spec.key):
                data = inputs(); del data[spec.key]
                result = run(data)
                self.assertEqual(result["status"], "NO_SCORE")
                self.assertIsNone(result["experimental_score"])
                self.assertEqual(result["coverage"], {"present":9, "required":10})

    def test_invalid_values_boolean_and_nonfinite(self):
        for value in [True, float("nan"), float("inf"), -2, "1"]:
            with self.subTest(value=value):
                data = inputs(); key = FACTORS[0].key
                data[key] = replace(data[key], value=value)
                self.assertIsNone(run(data)["experimental_score"])

    def test_units_identity_hash_and_available_basis_are_required(self):
        for patch in [dict(unit="percent"), dict(identity_confirmed=False),
                      dict(sha256="missing"), dict(source_ref=""),
                      dict(availability_basis="SEC_ACCEPTED")]:
            data = inputs(); key = FACTORS[0].key
            data[key] = replace(data[key], **patch)
            self.assertEqual(run(data)["status"], "NO_SCORE")

    def test_no_future_or_retrospective_observation(self):
        key = FACTORS[0].key
        for field in ["period_end", "available_at", "observed_at"]:
            data = inputs()
            data[key] = replace(data[key], **{field: NOW+timedelta(seconds=1)})
            self.assertIn(key+":TIME_LEAK_OR_ORDER", run(data)["issues"])

    def test_time_order_and_naive_timestamp(self):
        data = inputs(); key = FACTORS[0].key
        data[key] = replace(data[key], available_at=NOW-timedelta(days=1))
        self.assertEqual(run(data)["status"], "NO_SCORE")
        data[key] = replace(data[key], period_end=NOW.replace(tzinfo=None))
        self.assertIn(key+":INVALID_TIME", run(data)["issues"])
        with self.assertRaises(ValueError):
            experiment(inputs(), as_of=NOW.replace(tzinfo=None), acknowledge_unapproved_experiment=True)

    def test_stale_and_derived_catalyst_age(self):
        data = inputs(); key = "quoted_spread_bps"
        data[key] = replace(data[key], period_end=NOW-timedelta(hours=2))
        self.assertIn(key+":STALE", run(data)["issues"])
        data = inputs(); key = "catalyst_age_hours"
        data[key] = replace(data[key], value=59)
        self.assertIn(key+":AGE_MISMATCH", run(data)["issues"])

    def test_unknown_factor_cannot_sneak_in(self):
        data = inputs(); data["future_label"] = data[FACTORS[0].key]
        self.assertIn("UNKNOWN_FACTORS", run(data)["issues"])

    def test_normalization_clamps_and_risk_penalties_bound_score(self):
        data = inputs()
        for spec in FACTORS:
            value = spec.low if spec.reverse else spec.high
            end = NOW-timedelta(hours=value if spec.key == "catalyst_age_hours" else .5)
            data[spec.key] = replace(data[spec.key], value=value, period_end=end, available_at=end, observed_at=end)
        for spec in RISKS:
            data[spec.key] = replace(data[spec.key], value=spec.low)
        self.assertEqual(run(data)["experimental_score"], 100)
        for spec in RISKS:
            data[spec.key] = replace(data[spec.key], value=spec.high*2)
        self.assertEqual(run(data)["experimental_score"], 55)

    def test_replay_counts_and_no_outcome_leak_into_features(self):
        cases = [ReplayCase(str(i), NOW, inputs(), NOW+timedelta(days=1),
                            NOW+timedelta(days=2), outcome) for i,outcome in enumerate([.1,-.1])]
        result = evaluate_frozen_replay(cases, evaluation_as_of=NOW+timedelta(days=3),
                                       alert_threshold=20, positive_return_threshold=.05,
                                       acknowledge_unapproved_experiment=True)
        self.assertEqual(result["counts"], dict(tp=1, fp=1, tn=0, fn=0))
        self.assertEqual(result["precision"], .5)
        self.assertEqual(result["false_positive_rate"], 1)
        self.assertEqual(result["false_alert_fraction"], .5)
        self.assertFalse(result["canonical"])

    def test_replay_unmatured_future_features_and_duplicate_cases(self):
        valid = ReplayCase("valid", NOW, inputs(), NOW+timedelta(days=1), NOW+timedelta(days=2), .1)
        late = replace(valid, case_id="late", label_available_at=NOW+timedelta(days=4))
        leaky = inputs(); key = FACTORS[0].key
        leaky[key] = replace(leaky[key], observed_at=NOW+timedelta(days=1))
        future = replace(valid, case_id="future", evidence=leaky)
        kwargs = dict(evaluation_as_of=NOW+timedelta(days=3), alert_threshold=100,
                      positive_return_threshold=.05, acknowledge_unapproved_experiment=True)
        result = evaluate_frozen_replay([valid,late,future], **kwargs)
        self.assertEqual(result["counts"], dict(tp=0, fp=0, tn=0, fn=1))
        self.assertEqual(len(result["excluded"]), 2)
        self.assertIsNone(result["precision"])
        with self.assertRaises(ValueError):
            evaluate_frozen_replay([valid,valid], **kwargs)

    def test_replay_requires_explicit_acknowledgement_and_valid_threshold(self):
        kwargs = dict(evaluation_as_of=NOW, alert_threshold=50, positive_return_threshold=.05)
        with self.assertRaises(ValueError):
            evaluate_frozen_replay([], **kwargs)
        kwargs["alert_threshold"] = float("nan")
        with self.assertRaises(ValueError):
            evaluate_frozen_replay([], acknowledge_unapproved_experiment=True, **kwargs)


if __name__ == "__main__":
    unittest.main()
