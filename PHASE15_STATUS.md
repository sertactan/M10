# Phase 15 — Historical OOS Ranking Validation (source-gated)

Status: **CODE REVIEW / CI REQUIRED; REAL-DATA PERFORMANCE BLOCKED** (2026-10-08).

This phase evaluates frozen WF6 OOS candidates using an **explicitly chosen
WF5 mature-label evidence batch** from Learning V2. It does not modify
canonical S15/S16 formulas, execute trades, fit models, invent missing labels,
or claim to have tested the full historical US market.

## What is calculated

For every fully labelled snapshot date (with **every** WF6 candidate in that
date READY, score present, score identical to source evidence, matching security
ID, observation ID, FM252, 2X/5X/10X time-to-hit and mature label available by
the evaluation cutoff):

- `Precision@K`: among highest frozen S15.3 V1.4.1 scores, the fraction
  with source-defined `FM252 >= 10` within the canonical horizon.
- `Recall@K within source cohort`: of all known 10X winners in that
  **fully labelled WF6 date**, the fraction selected in top K.
  **Not** full-US universe recall, which requires independently verified PIT
  historical membership and delisting coverage.
- `10X base rate`: within that complete source cohort, not an industry
  matched-control baseline.
- Counts of missing/immature/censored/date-incomplete observations.
- SHA256 of deterministic report contents for reproducible comparisons.

A date with ANY missing/mismatched label, missing score, immature outcome or
censored observation is excluded completely to prevent misleading win-rate
inflation. A date with fewer than K candidates cannot produce Precision@K.
Fold overlaps (same security/date in two folds) are rejected. Zero true
winners => recall undefined (`null`), not zero or 100%.

## Run only on the Windows M10 system containing real data

Prerequisites: successfully completed canonical WF5, WF6 and a Learning V2
`wf5-labels-import` batch. Identify both original run IDs and the batch hash
from the original import report. Do **not** pass placeholder strings.

```powershell
python scripts/phase15_oos_evaluation.py `
  --operational-db data/runtime/operational.db `
  --learning-db data/runtime/meridyen_learning.sqlite3 `
  --wf6-run-id <REAL_COMPLETE_WF6_RUN_ID> `
  --wf5-batch-sha256 <REAL_WF5_BATCH_SHA256> `
  --cutoff 2026-10-08 `
  --k 10 20 `
  --out data/runtime/phase15_oos_audit.json
```

Backtest **data prerequisites still outstanding**: Actual local M10
operational.db/Parquet price histories, 144 PIT month-end company universes,
delisted stocks, issuer filing as-of provenance and WF9
`COMPLETE_AND_ACTIVATED` evidence have not been accessed from this remote
session. A GitHub Actions CI pass verifies code only, not investment returns.

## Important accuracy fix included

The existing canonical `FM252` definition is **maximum achieved adjusted
multiple over the 252-session observation window**, NOT final day close.
Verified delisting terminal consideration can establish a 10X magnitude
without a known trading-session `time_to_10x_sessions`. The Learning V2
importer now handles such terminal evidence only when
`terminal_horizon_verified` and `terminal_source_ref` exist; otherwise
incomplete 252-session paths stay censored.

## Not part of this phase's metrics yet

True market-wide 10X recall and precision, matched-controls, risk/transaction
costs, SPY/QQQ comparison, P&L simulation, probability calibration, and
ML challenger promotion require independent full-universe PIT readiness
and separate validation. No release of this code asserts any of those.
