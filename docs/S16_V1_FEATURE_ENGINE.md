# S16 V1.0 — Canonical Feature Engine Completion

Status: **CANONICAL SUBFEATURE IMPLEMENTATION**

This document completes the feature-level math under the already frozen
`S16V1Model`. Core V1 weights/gates/caps are unchanged.

## ShortPressure

```
ShortPressure =
  0.50 SI_to_Float
+ 0.20 DaysToCover
+ 0.15 BorrowPressure
+ 0.10 FTDPressure
+ 0.05 ShortInterestAcceleration
```

All legs are 0–100 PIT scores. Missing legitimate archive legs are excluded and
weights are renormalized. At least one core exchange short-interest leg
(SI/Float or DaysToCover) is required; borrow/FTD alone cannot manufacture a
short signal.

ShortInterestAcceleration uses the two most recent short-interest records that
were actually available at the as-of timestamp.

## VolumeIgnition

```
VolumeIgnition =
  0.40 RVOL
+ 0.30 FloatTurnover
+ 0.20 VolumeAcceleration
+ 0.10 PremarketTurnover
```

Daily historical data derives:
- RVOL = current volume / prior 20-session average volume
- FloatTurnover = current volume / PIT float
- VolumeAcceleration = current volume / prior 5-session average volume

PremarketTurnover is optional PIT evidence. If unavailable, the first three
weights are renormalized; premarket is never backfilled.

## MomentumAcceleration

```
MomentumAcceleration =
  0.35 Return1D
+ 0.25 ReturnAcceleration
+ 0.20 RangeExpansion
+ 0.20 CloseLocation
```

where:

```
ReturnAcceleration = R1D - R5D / 5
RangeExpansion = current normalized intraday range / prior 20-session average range
CloseLocation = (Close - Low) / (High - Low)
```

Each raw leg is normalized cross-sectionally on the exact same date before the
canonical weighted composite is calculated.

## Catalyst

```
Catalyst =
  0.25 Materiality
+ 0.20 Surprise
+ 0.15 Credibility
+ 0.15 MarketCapImpact
+ 0.10 Novelty
+ 0.15 Immediacy
```

A subcomponent composite requires at least four of the six canonical legs.
Otherwise the engine uses the explicit PIT catalyst fallback if one exists.
A single strong subcomponent cannot create a 100 Catalyst score.

## Attention / Social

SocialVelocity combines:

```
SocialVelocity =
  0.70 MentionVelocity
+ 0.30 UniqueAuthorVelocity
```

and applies a concentration penalty of up to 25% when a burst is dominated by a
small number of authors.

The PRE Attention score uses:

```
Attention =
  0.45 SocialVelocity
+ 0.25 NewsVelocity
+ 0.20 SearchVelocity
+ 0.10 CrossPlatformConfirmation
```

Missing legitimate channels are renormalized. CrossPlatformConfirmation measures
how many available channels are simultaneously running at >=2x their own
20-day baseline.

## Point-in-time rules

1. No evidence may be used before `available_at`.
2. Missing archive evidence is not zero.
3. Short-sale volume is not short interest.
4. Premarket data is optional and never synthesized from daily bars.
5. Search/social/news counts must be historical observations, not current counts
   projected backward.
6. All cross-sectional percentiles are computed on the exact observation date.
7. Core S16 V1 model weights are unchanged by this feature-engine completion.

## Implementation

- `core/historical/s16_feature_engine.py`
- `core/historical/s16_reconstruction.py`
- `scripts/materialize_s16_historical_features.py`
- `data/providers/s16_archive_csv.py`

Feature engine version:

```
S16_FEATURE_ENGINE_V1.0
```

Historical reconstruction version:

```
s16-historical-reconstruction-v3-feature-complete
```
