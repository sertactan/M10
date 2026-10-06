# S16 — Explosive 1-Week 10X Discovery

Status: V0.2 baseline implemented; V0.3 false-positive-resistant challenger implemented.

## Goal

Rank US common stocks for explosive 1–5 trading-session moves and separately label
3x / 5x / 10x forward outcomes. S16 is an event-driven discovery model, not a
long-horizon company-quality model.

## V0.2 baseline

FUEL = 0.35 FloatScarcity + 0.27 ShortPressure + 0.18 FloatTurnover
     + 0.12 LiquidityElasticity + 0.08 OwnershipLock

SPARK = 0.32 Catalyst + 0.25 VolumeIgnition + 0.18 MomentumAcceleration
      + 0.10 SocialVelocity + 0.08 NewsVelocity + 0.07 RegimeSympathy

RiskPenalty = 25 * (
    0.40 DilutionRisk + 0.20 ExtensionRisk + 0.15 DataRisk
  + 0.15 LiquidityRisk + 0.10 ManipulationRisk
)

IGNITION_V02 = clamp(sqrt(FUEL * SPARK) + ConvergenceBonus - RiskPenalty)

ARMED_V02 = clamp(
    0.45 FUEL + 0.15 ShortPressure + 0.12 Attention + 0.10 Compression
  + 0.08 CatalystProximity + 0.05 Theme + 0.05 Anomaly - RiskPenalty
)

V0.2 is frozen as the baseline even though ShortPressure is counted both inside
FUEL and explicitly in ARMED. This lets V0.3 be evaluated honestly against it.

## False-signal stress result

12 hard-negative archetypes were locked as a regression test.

- V0.2 WATCH (ARMED >= 50): 8 / 12 false alerts.
- V0.2 ARMED (ARMED >= 60): 0 / 12.
- V0.2 IGNITION_WATCH (IGNITION >= 75): 0 / 12.
- V0.3 WATCH: 2 / 12.
- V0.3 non-IPO ARMED: 0 / 11.
- V0.3 IGNITION_WATCH: 0 / 12.

This is a formula stress test, not a market precision estimate.

## V0.3 challenger

V0.3 removes the explicit ShortPressure leg from ARMED. Short pressure remains
exactly once inside FUEL.

EARLY_SPARK = 0.25 Attention + 0.15 Compression + 0.25 CatalystProximity
            + 0.15 Theme + 0.20 Anomaly

ARMED_V03_BASE = sqrt(FUEL * EARLY_SPARK) + EarlyConvergenceBonus - RiskPenalty

Independent pillar gates cap the score when FUEL/EARLY_SPARK coverage is weak,
when too few independent pre-ignition pillars are present, when a move is already
extended without a proximate catalyst, or when dilution risk is extreme.

CONTINUATION = sqrt(VolumeIgnition * MomentumAcceleration)

IGNITION_V03 = clamp(
    0.72 * sqrt(FUEL * SPARK)
  + 0.28 * CONTINUATION
  + ConvergenceBonus
  - RiskPenalty
)

A strong ignition requires:
- VolumeIgnition >= 70
- MomentumAcceleration >= 60
- at least one independent driver >= 60 from Catalyst, SocialVelocity,
  ShortPressure, or RegimeSympathy.

## 5-session labels

The S16 outcome engine computes both adjusted-high and adjusted-close maximum
favorable excursion across the next five trading sessions.

- Y3X_HIGH / Y5X_HIGH / Y10X_HIGH
- Y3X_CLOSE / Y5X_CLOSE / Y10X_CLOSE

High and close labels are deliberately separate so intraday squeezes are not
misrepresented as close-to-close 10x events.

## 31 positive events

data/seeds/s16_positive_events.csv contains the 31 seed events supplied for the
pilot research set. IPO events are marked into an IPO control pool.

## 31 x 50 matched-control cohort

data/seeds/s16_matched_control_manifest.csv contains exactly 1,550 deterministic
match slots: 50 per positive event.

Actual control identities MUST be filled from a historical PIT universe. The
selector in core/historical/s16_controls.py uses only information available at
the matching date and excludes future outcomes from the distance function.

Match weights:

- market cap 22%
- float shares 20%
- ADV20 15%
- price 12%
- realized volatility 20d 12%
- momentum 5d 8%
- momentum 20d 5%
- sector 4%
- listing age 2%

IPO rows are only matched to IPO-route candidates.

The manifest intentionally remains PENDING_PIT_MATCH until the runtime historical
store contains the required point-in-time snapshots. Filling those 1,550 rows
with invented/current-survivor names would invalidate the experiment.

Use scripts/build_s16_matched_controls.py once PIT snapshots are exported.

## Next acceptance gate

Do not promote V0.3 to canonical until the 31 positives and 1,550 real controls
have labels joined only after matching. Report Precision/Recall by threshold,
Precision@K, FPR, and 3x/5x/10x performance separately.
