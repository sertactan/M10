# V1.4 Router and Gate Specification — Recovered Final

V1.4 retains canonical V1.2 primary/secondary model routes `F10/I10/D10/B10/R10/Q10`.

The V1.4 destination sub-router adds `SPIN/CYCLE/ASSET` activation using the exact gate
formulas frozen in the factor definitions. Active destination routes are ranked by gate score.

## Early Asymmetric Acceleration eligibility

EA10 runs only when:

```text
S15.3_V1.2 >= 65
M10_D >= 65
AND (M10_C < 70 OR DMG > 10)
```

```text
CGC = AccelScore(DMG_t-3m - DMG_t; 15)
```

Cycle:

```text
CA10 = WA(
  0.25 DEMA,
  0.20 SCTA,
  0.20 MCA,
  0.15 CAPA,
  0.10 DRA,
  0.10 CGC
)
```

Asset:

```text
AA10 = WA(
  0.25 RQA,
  0.20 TDA,
  0.15 FRA,
  0.15 CRA,
  0.15 DRA,
  0.10 CGC
)
```

```text
EA10 = CA10 for CYCLE
EA10 = AA10 for ASSET
```

## ProgressGate

PASS if at least 2 of 4 are true:

```text
DRA >= 70
CGC >= 60
RouteEvidenceAccel >= 70
MI >= 60
```

## EA score adjustment

```text
EAB = min(5, 0.40 * (EA10 - 65))
```

only when `EA10 >= 75` and `ProgressGate=PASS`; otherwise `EAB=0`.

```text
ESP = min(4, 0.20 * max(0, 55 - EA10))
S15.3_V1.4_FINAL = Clip(S15.3_V1.4_BASE + EAB - ESP)
```

If `M10_C < 70`:

```text
S15.3_V1.4_FINAL <= 79
```

EA labels:

```text
EA10 >=75 + ProgressGate PASS -> EARLY_ACCELERATING_10X
60 <= EA10 <75               -> EARLY_ASYMMETRIC_WATCH
EA10 <60                      -> EARLY_ASYMMETRIC_STALLED
```
