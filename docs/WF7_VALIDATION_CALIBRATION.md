# WF7 — OOS Validation & Empirical Magnitude Calibration

Status: STARTED.

Policy: `WF7_VALIDATION_POLICY_V1_2026-10-07`.

WF7 consumes only WF6 **out-of-sample READY** observations.

## Denominators

- CENSORED/PARTIAL rows are excluded from realized-outcome denominators.
- A missing V1.4.1 score is not a failure.
- Market 10X base rate uses all READY OOS observations.
- Score-threshold metrics use READY observations with an available V1.4.1 score.

## Primary metrics

```text
BaseRate10X
Precision@65 / Recall@65 / Lift@65
Precision@75 / Recall@75 / Lift@75
Precision@80 / Recall@80 / Lift@80
Precision@85 / Recall@85 / Lift@85
Precision@Top20 / Lift@Top20
Precision@Top50 / Lift@Top50
NearMissRate
MagnitudeFPRate
StrongWinnerFPRate
HardFPRate
MedianFM252
MedianTimeTo10X
PR-AUC (standard average precision)
Route-level 5X/10X rates
```

## Score-bucket empirical calibration

Buckets:

```text
<55
55-64
65-74
75-79
80-84
85+
```

Observed 2X/5X/7X/10X rates are released only when N>=30.
N=30-49 is REDUCED_SAMPLE; N>=50 NORMAL.

The S15.3 score itself is **not a probability**. Probability calibration error
is therefore not reported until an explicit probability head exists.
