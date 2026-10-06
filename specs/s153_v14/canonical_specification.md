# S15.3 V1.4 Canonical Specification — Recovered Final

Canonical formula version: `S15.3_V1.4_RECOVERED_2026-10-05`.

This file freezes the latest exact V1.4 core recovered from the prior model-development work.

## Dual magnitude

```text
M10_D = M10_v1.2
M10_C = M10_v1.3
DMG   = M10_D - M10_C
```

Confirmation bonus:

```text
CB = min(3, 0.30 * (M10_C - 65))
```

only when `M10_C >= 65` and `DMG <= 10`; otherwise `CB=0`.

Disagreement penalty:

```text
DP = min(4, 0.20 * max(0, DMG - 10))
```

Base V1.4 score:

```text
S15.3_V1.4_BASE = Clip(S15.3_V1.2 + CB - DP)
```

## Classification gates

Precision Confirmed requires all:

```text
not EARLY_ASYMMETRIC
S15.3_V1.4 >= 80
M10_D >= 70
M10_C >= 70
T10 >= 70
DF10_C >= 60
XR >= 99
HMG10 available
RouteGate = PASS
Confidence >= 70
```

Strong Watch:

```text
not EARLY_ASYMMETRIC
S15.3_V1.4 >= 75
M10_D >= 65
M10_C >= 65
T10 >= 65
```

Early Asymmetric:

```text
S15.3_V1.2 >= 65
AND (M10_C < 65 OR DMG > 10)
```

Large `DMG` therefore cannot be promoted to Precision Confirmed.

## Probability rule

V1.4 scores are not literal probabilities. Large-winner probabilities and probability buckets
must come from Phase 8 market-prevalence / walk-forward calibration. UI example percentages
are not canonical mappings.
