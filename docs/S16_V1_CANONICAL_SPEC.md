# S16 V1.0 CANONICAL — Explosive 1-Week Discovery

Status: **FROZEN CANONICAL CORE FORMULA**

Purpose: rank US common stocks for explosive 1–5 trading-session setups.  
Targets are evaluated separately as 3x / 5x / 10x HIGH and CLOSE outcomes.

V1.0 freezes the ranking/state formula. Future historical work may calibrate:
- alert thresholds,
- route-specific reporting,
- 3x / 5x / 10x probability heads.

Those calibration steps MUST NOT silently change the V1.0 weights below. A
formula change requires a new explicit model version.

---

## 1. Input scale

All positive signal inputs are normalized to 0–100.

Risk inputs are normalized to 0–1:

- DilutionRisk
- ExtensionRisk
- DataRisk
- LiquidityRisk
- ManipulationRisk

Point-in-time data discipline is mandatory. Missing evidence is not zero.

---

## 2. Structural Fuel

```
FUEL =
  0.26 MarketCapScarcity
+ 0.30 FloatScarcity
+ 0.18 ShortPressure
+ 0.10 FloatTurnover
+ 0.08 LiquidityElasticity
+ 0.08 OwnershipLock
```

Interpretation:

- MarketCapScarcity: same-date inverse percentile of log market capitalization.
- FloatScarcity: same-date inverse percentile of log tradable/free float.
- ShortPressure: short-interest stress composite.
- FloatTurnover: volume / tradable float, cross-sectionally normalized.
- LiquidityElasticity: price-move sensitivity to limited dollar liquidity.
- OwnershipLock: evidence-backed reduction in effectively tradable supply.

Micro-cap and low-float are deliberately separate factors.

---

## 3. ShortPressure canonical sub-composite

When all legs exist:

```
ShortPressureRaw =
  0.50 SI_to_Float
+ 0.20 DaysToCover
+ 0.15 BorrowPressure
+ 0.10 FTDPressure
+ 0.05 ShortInterestAcceleration
```

Each leg is first converted to a same-date 0–100 percentile.

If a legitimate historical leg is unavailable, the available weights are
renormalized. A missing short-interest archive itself is NOT interpreted as zero.

Short-sale volume is never substituted for short interest.

Short evidence is aged using its real publication / availability timestamp.

---

## 4. Pre-Ignition Readiness

```
PRE =
  0.20 Attention
+ 0.18 Compression
+ 0.22 CatalystProximity
+ 0.12 Theme
+ 0.18 Anomaly
+ 0.10 RegimeSympathy
```

This is the pre-explosion setup layer.

Attention represents point-in-time abnormal attention evidence.  
Compression rewards a quiet/coiled setup before expansion.  
CatalystProximity measures known upcoming event proximity, not future knowledge.  
Anomaly captures early abnormal price/volume behavior.  
RegimeSympathy captures same-theme/peer explosive behavior.

---

## 5. ARMED score

The base is a weighted geometric mean:

```
ARMED_BASE = GM(
  FUEL weight 0.55,
  PRE  weight 0.45
)
```

Equivalent:

```
ARMED_BASE = exp(
  0.55 ln(FUEL) +
  0.45 ln(PRE)
)
```

Implementation floors individual geometric inputs at 1 for numerical stability.

### ARMED convergence pillars

One point is counted for each independent condition:

1. FUEL >= 65
2. Attention >= 60
3. CatalystProximity >= 60
4. max(Compression, Anomaly) >= 65
5. max(Theme, RegimeSympathy) >= 60

```
ARMED_BONUS = min(8, 2 * max(0, Pillars - 2))
```

### ARMED risk

```
ARMED_RISK = 22 * (
  0.35 DilutionRisk
+ 0.15 ExtensionRisk
+ 0.20 DataRisk
+ 0.15 LiquidityRisk
+ 0.15 ManipulationRisk
)
```

```
ARMED = clamp(
  ARMED_BASE + ARMED_BONUS - ARMED_RISK,
  0, 100
)
```

### ARMED hard caps

- FUEL < 50 OR PRE < 50 -> ARMED <= 49
- fewer than 3 independent ARMED pillars -> ARMED <= 59
- DilutionRisk >= 0.80 -> ARMED <= 49
- DataRisk >= 0.60 -> ARMED <= 59
- ExtensionRisk >= 0.65 AND CatalystProximity < 70 -> ARMED <= 59

---

## 6. Ignition Spark

```
SPARK =
  0.30 Catalyst
+ 0.22 VolumeIgnition
+ 0.18 MomentumAcceleration
+ 0.10 FloatTurnover
+ 0.08 SocialVelocity
+ 0.05 NewsVelocity
+ 0.07 RegimeSympathy
```

### Catalyst canonical sub-composite

When full evidence exists:

```
Catalyst =
  0.25 Materiality
+ 0.20 Surprise
+ 0.15 Credibility
+ 0.15 MarketCapImpact
+ 0.10 Novelty
+ 0.15 Immediacy
```

No catalyst score may use a filing/news item before its actual availability time.

### VolumeIgnition canonical sub-composite

```
VolumeIgnition =
  0.40 RVOL
+ 0.30 FloatTurnover
+ 0.20 VolumeAcceleration
+ 0.10 PremarketTurnover
```

If premarket data is unavailable in a historical daily dataset, legitimate
available legs are renormalized; it is not backfilled.

### MomentumAcceleration canonical sub-composite

```
MomentumAcceleration =
  0.35 R1D
+ 0.25 ReturnAcceleration
+ 0.20 RangeExpansion
+ 0.20 CloseLocationContinuation
```

where a core acceleration measure is:

```
ReturnAcceleration = R1D - R5D / 5
```

---

## 7. Continuation

```
CONTINUATION = sqrt(
  VolumeIgnition * MomentumAcceleration
)
```

A move with volume but no price acceleration, or price acceleration without
volume confirmation, is deliberately suppressed.

---

## 8. IGNITION score

Base weighted geometric mean:

```
IGNITION_BASE = GM(
  FUEL         weight 0.30,
  SPARK        weight 0.45,
  CONTINUATION weight 0.25
)
```

Equivalent:

```
IGNITION_BASE = exp(
  0.30 ln(FUEL)
+ 0.45 ln(SPARK)
+ 0.25 ln(CONTINUATION)
)
```

### IGNITION pillars

1. FUEL >= 60
2. Catalyst >= 70
3. VolumeIgnition >= 75
4. MomentumAcceleration >= 65
5. max(Catalyst, SocialVelocity, NewsVelocity, ShortPressure, RegimeSympathy) >= 65

```
IGNITION_BONUS = min(10, 2.5 * max(0, Pillars - 2))
```

### IGNITION risk

```
IGNITION_RISK = 25 * (
  0.35 DilutionRisk
+ 0.25 ExtensionRisk
+ 0.15 DataRisk
+ 0.10 LiquidityRisk
+ 0.15 ManipulationRisk
)
```

```
IGNITION = clamp(
  IGNITION_BASE + IGNITION_BONUS - IGNITION_RISK,
  0, 100
)
```

---

## 9. Ignition Gate

A true ignition requires all three:

```
VolumeIgnition >= 65
MomentumAcceleration >= 55
IndependentDriver >= 60
```

where:

```
IndependentDriver =
max(
  Catalyst,
  SocialVelocity,
  NewsVelocity,
  ShortPressure,
  RegimeSympathy
)
```

If the gate fails:

```
IGNITION <= 69
```

Additional caps:

- DilutionRisk >= 0.80 and Catalyst < 90 -> IGNITION <= 69
- ExtensionRisk >= 0.80 and Catalyst < 85 -> IGNITION <= 64
- ManipulationRisk >= 0.80 -> IGNITION <= 59
- DataRisk >= 0.60 -> IGNITION <= 74

---

## 10. Final S16 Explosive Score

Before confirmed ignition:

```
S16_EXPLOSIVE = ARMED
```

After the Ignition Gate is open:

```
S16_EXPLOSIVE =
  0.30 ARMED
+ 0.70 IGNITION
```

The final score is clamped to 0–100.

This deliberately gives the real-time ignition state more weight once an actual
volume/momentum/driver convergence is observed.

---

## 11. State Engine

Canonical reporting states:

- 0–49: DORMANT
- 50–59: WATCH
- 60–74: ARMED
- >=75 ARMED with no ignition gate: STRONG_ARMED
- ignition gate + IGNITION 70–79: IGNITION_WATCH
- ignition gate + IGNITION 80–89: IGNITION
- ignition gate + IGNITION >=90: EXTREME_IGNITION

Route labels (BIO, SQUEEZE, MEME, DE-SPAC, CRYPTO, IPO, etc.) are explanatory.
V1.0 does NOT change formula weights by route.

---

## 12. 3x / 5x / 10x outputs

S16 V1.0 score is NOT a probability.

Do not report:

```
S16=90 => 90% chance of 10x
```

Probability heads are separate calibrated outputs:

```
P(>=3x within 5 sessions)
P(>=5x within 5 sessions)
P(>=10x within 5 sessions)
```

They may only be fitted from leakage-safe, unbiased historical market prevalence
data after the canonical V1.0 score is frozen.

---

## 13. Outcome labels

Both high and close variants remain mandatory:

```
MFE5_HIGH  = max(adjusted high t+1..t+5) / entry
MFE5_CLOSE = max(adjusted close t+1..t+5) / entry
```

Labels:

- Y3X_HIGH / Y5X_HIGH / Y10X_HIGH
- Y3X_CLOSE / Y5X_CLOSE / Y10X_CLOSE

Intraday-only and IPO-offer-price explosions remain explicitly tagged routes /
measurement classes rather than being silently mixed with strict prior-close
five-session 10x events.

---

## 14. Version governance

Canonical implementation:

```
S16V1Model
version = "S16_V1.0_CANONICAL"
```

V0.2 and V0.3 remain frozen for historical A/B comparison.

Any future change to the V1.0 core weights, gates, caps, or risk equations
requires a new explicit version (for example S16 V1.1). Threshold/probability
calibration may be updated only as separately versioned calibration evidence.
