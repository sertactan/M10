# WF7 — Validation and Empirical Calibration

Status: STARTED.

Policy: `WF7_VALIDATION_POLICY_V1_2026-10-07`.

WF7 consumes **WF6 out-of-sample READY observations only**. CENSORED rows are
kept for coverage reporting but never converted to failures.

Canonical validation outputs:

```text
Precision@80
Recall@80
Precision@75
Recall@75
Precision@Top20
Precision@Top50
Lift@20
Lift@50
PR-AUC
NearMissRate@80
MagnitudeFPRate@80
HardFPRate@80
MedianLeadTime
MedianForwardMaxMultiple
```

WF7 also emits empirical score-band frequencies for 2X/5X/10X. These are
historical calibration observations, not a claim that S15.3 score itself is a
probability.

Thresholds 75 and 80 remain the frozen canonical thresholds. WF7 does not tune
thresholds on the final holdout.
