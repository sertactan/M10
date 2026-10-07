from __future__ import annotations

LEAKAGE_POLICY_VERSION = "WF6_LEAKAGE_POLICY_V1_2026-10-07"

# Frozen model: WF6 validates the existing model and never fits/re-weights it.
MODEL_TUNING_ALLOWED = False

# Same-security observations from earlier dates may exist in the historical
# panel, but they must not enter the target security's similarity cohort.
EXCLUDE_TARGET_SECURITY_FROM_HISTORICAL_CONTROLS = True
