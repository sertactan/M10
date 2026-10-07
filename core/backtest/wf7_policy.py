from __future__ import annotations

POLICY_VERSION = "WF7_VALIDATION_POLICY_V1_2026-10-07"
THRESHOLD_VERSION = "S153_CANONICAL_THRESHOLDS_75_80_V1"

# Canonical S15.3 thresholds are evaluated, not re-fitted by WF7.
STRONG_WATCH_THRESHOLD = 75.0
PRECISION_THRESHOLD = 80.0
ALLOW_HOLDOUT_THRESHOLD_TUNING = False

# Probability-like calibration is empirical frequency only; score != probability.
MIN_CALIBRATION_N = 30
FULL_CALIBRATION_N = 50
