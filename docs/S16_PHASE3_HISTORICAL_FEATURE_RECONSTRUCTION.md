# S16 Phase 3 — Historical Feature Reconstruction

Status: implementation complete; historical external archives remain runtime inputs.

## Objective

Reconstruct the exact S16 feature vector that could have been known at each
historical observation time for:

- 31 positive seed events
- 1,550 contemporaneous matched controls
- 1,581 observations total

No future information may enter a score.

## Evidence layers

### 1. Price / liquidity layer

Derived from one adjusted single-provider price series for the exact as-of date:

- float_scarcity
- float_turnover
- liquidity_elasticity
- volume_ignition
- momentum_acceleration
- compression
- anomaly
- extension_risk
- liquidity_risk

Normalization is cross-sectional against the same-date US candidate universe.
This avoids hard-coding one liquidity/volatility regime across 2015–2026.

### 2. Short-interest layer

Stored in s16_short_interest_source.

Required fields include:

- settlement_date
- short_interest
- available_at
- source / source_ref

Optional:

- avg_daily_volume
- float_shares
- days_to_cover

The model filters on available_at, not settlement_date. A position report is
never made visible before its actual publication/availability timestamp.

Daily short-sale volume is not accepted as a replacement for short interest.

### 3. Attention layer

Stored in s16_attention_source.

Channels:

- SOCIAL
- NEWS
- SEARCH

The canonical Phase 3 velocity calculation compares the latest one-day mention
sum against the previous 20 calendar days' average daily mention count. Missing
history remains missing.

### 4. Direct point-in-time evidence

Stored in s16_feature_evidence_source.

Supported direct features:

- ownership_lock
- catalyst
- regime_sympathy
- catalyst_proximity
- theme
- dilution_risk
- manipulation_risk

Values must already be normalized and evidenced by an archive or deterministic
upstream process. Risk fields use [0,1]; other scores use [0,100].

The reconstruction layer does not invent a catalyst score from the existence of
an 8-K alone.

## SEC coverage

The SEC provider now separates financial-fact forms from S16 event-history forms.

Financial fact forms remain:

- 10-K / 10-Q / 8-K
- 20-F / 40-F / 6-K
- amendments

Filing history additionally captures:

- S-1 / S-3
- F-1 / F-3
- 424B2 / 424B3 / 424B4 / 424B5
- EFFECT / RW
- proxy forms

Offering forms are available for S16 dilution research but are not treated as
financial-statement XBRL facts.

## Data-quality / leakage rules

1. Every timestamp must be timezone-aware.
2. available_at may never predate observed_at.
3. Short-interest available_at may never predate settlement_date.
4. Scores are reconstructed strictly at the observation as-of timestamp.
5. Missing external evidence remains missing; it is never replaced by zero.
6. S16 scoring fails closed unless all required inputs are present.
7. Current ticker identity must be resolved using historical aliases valid at the
   observation date.
8. Cross-provider price stitching remains forbidden.
9. All derived model features retain source/evidence metadata.
10. Future 3x/5x/10x outcomes are joined only after scoring.

## Source coverage reality

Official exchange short-interest is semi-monthly. Current Nasdaq Data Link
Nasdaq Short Interest Report history begins in September 2022, so 2015–2022
events require an additional licensed/archive source if the full period is to
have real short-interest evidence.

Historical social attention similarly requires a point-in-time archive. Current
social counts must not be backfilled into old observations.

SEC submissions/XBRL data can be reconstructed from EDGAR filing history with
acceptance timestamps. Filing acceptance is used conservatively as the point at
which the filing may enter a historical model snapshot.

## Runtime pipeline

1. Import short-interest archive:
   scripts/import_s16_short_interest.py

2. Import NEWS/SOCIAL attention archives:
   scripts/import_s16_attention.py

3. Import direct normalized PIT evidence:
   scripts/import_s16_feature_evidence.py

4. Build the 1,581 observation manifest:
   scripts/build_s16_observation_manifest.py

5. Reconstruct historical features:
   scripts/materialize_s16_historical_features.py

6. Score V0.2 and V0.3:
   scripts/score_s16_historical_features.py

7. Join five-session outcomes after scoring.

8. Run:
   scripts/run_s16_case_control_benchmark.py

## Acceptance gate

Phase 3 code is complete when CI passes.

The historical dataset is considered COMPLETE only when:

- 31 positive observations exist
- 1,550 controls exist
- all 1,581 rows have real PIT price coverage
- all 1,581 rows have required short/social/news/direct evidence or are explicitly
  excluded by a predeclared missing-data protocol
- V0.2/V0.3 scores are generated before future outcomes are joined

Until then, the benchmark must report BLOCKED_PIT_FEATURE_COVERAGE rather than
fabricating values.
