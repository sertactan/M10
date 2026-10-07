# WF4 — Historical Controls

Status: COMPLETE — policy/engine foundation.

Policy version: `WF4_HISTORICAL_POLICY_V1_2026-10-07`.

## Leakage firewall

A historical observation can enter a target cohort only when:

```text
label_available_at <= target_as_of
```

Outcome labels are never used in the target feature vector.

## H10 / HMG10

Uses the recovered canonical formulas:
- TRUE_10X: FM252 >= 10
- near miss: 7 <= FM252 < 10
- hard: FM252 < 3
- MeanTop5 similarity

## HMG5 explicit policy

The canonical source states M5 uses the historical 5X cohort. WF4 Policy V1
freezes:
- winner5: FM252 >= 5
- near5: 3 <= FM252 < 5
- hard: FM252 < 3

and applies the same magnitude-similarity structure used by HMG10.

## XR

Canonical exact cohort:
`AsOfMonth x Route x MarketCapBucket`.

If exact N<50, Policy V1 expands to same month x route across buckets.
If expanded N<30, XR=N/A. Ties use midrank percentile.

## Outputs

```text
WINNER_SIM
CONTROL_SIM
H10
HMG5
HMG10
XR
```

All outputs retain cohort counts and policy/vector versions in evidence.
