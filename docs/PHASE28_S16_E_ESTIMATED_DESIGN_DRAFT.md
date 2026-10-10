# S16-E Estimated — Unapproved Contract Design DRAFT v0.1

**Status: DESIGN_ONLY / NOT_APPROVED / NO_SCORE / NO_AUTOMATIC_ACTIVATION.**

The repository contains a frozen S16 V1.0 canonical model and separately
versioned S16-EA V1.3 event alert engine. No user-approved independent S16-E
numeric estimating contract was found. **This document does not introduce a
new S16-E numeric formula, default 50, substitute S16-EA, or grant canonical
status.** In the Phase28 UI, S16-E remains **N/A / SPEC_MISSING**.

## Proposed purpose / horizon

Screen for **research-only 1–5 trading-session asymmetric price movement**.
S16-C still requires all 22 frozen normalized PIT features, and S16-EA still
requires genuine 1m/5m intraday bars and precise UTC news event timestamps.
This draft does not alter either model.

## Candidate source-backed factor families

| Family | Real candidate inputs | Evidence requirements | If missing |
|---|---|---|---|
| Price / volume | Dated OHLCV; EMA/SMA20/50; 5-session change; RVOL20 | Exchange-local session, quote time, source ID, currency, provider snapshot hash; delayed/last trade explicitly labeled | MISSING |
| Liquidity / risk | Dollar volume, volatility, drawdown, spread *only if quoted* | Lookback length, no future bars, session-level normalization, reliable bid/ask for spread | MISSING |
| Supply / float | Dated share count, public float, actual short-interest publication date | Float and short sources must be separately validated; listed shares cannot stand in for float | MISSING |
| Catalyst | 8-K/filing/event release, earnings call and first public dissemination | Event type, primary source, UTC publication and retrieval times, de-duplicated catalyst family | MISSING |
| Quality / dilution | Filed cash, debt, FCF, SBC, share dilution | Period-matched filings, filing/availability; no future restatement backfill | MISSING |
| Regime | SPY/QQQ/IWM dated raw returns, breadth and volatility | Same-clock contemporaneous data, source/time hash | MISSING |

SEC local cache with `accepted_at=NULL` may be used in an explicitly labeled
current **research** diagnostic but cannot be claimed a canonical historic PIT
factor. Yahoo-compatible last trade is not a live exchange-certified quote.

## Missing-value and gate policy

1. Do **not** silently fill unknown float, short, catalyst, news, options,
   insider, social or risk values with 0, 50, means, or inferred negatives.
2. Missing a model's hard-required core pillar means **N/A**, not a lower
   confidence score with invented weights.
3. Coverage denominator, essential pillar set, hard no-score thresholds,
   scoring weights, risk penalties and the numerical score normalization all
   remain **TBD / USER APPROVAL REQUIRED**. This draft has no executable
   numerical estimator and does not authorize deployment.
4. List observed inputs with source URL, actual trade/filing time,
   `available_at`, license scope, original evidence hash, lookback, and
   metric meaning. Keep `observed_at` separate from `available_at`.
5. If any source violates freshness, license, identity, period or PIT gates,
   explicitly mark STALE_DATA / PROVIDER_ERROR / MISSING_DATA; retain cached
   observations only with their original timestamps.

## Confidence / uncertainty

Before numerical confidence is allowed, publish **qualitative** confidence
tags based on verified source coverage, stale inputs, independently confirmed
events and market-data alignment. No measured hit-rate, 10X probability, or
100-point confidence is possible without holdout validation.

## Calibration and test prerequisite

Design a frozen historical as-of replay with true provider availability,
delisted/corporate-action-adjusted outcomes and no label leakage. Evaluate
precision@K, false-alerts, OOS performance and drawdowns by market regime
before proposing any numeric weighting. Tests using artificial events check
software contracts only; they are not performance evidence.

**User approval needed:** specific 0–100 feature normalization rubrics,
minimum valid coverage, chosen scoring formula, hard gates, risk penalties and
explicit version activation. Until then **S16-E N/A**, **S16-C N/A** and
historical Canonical **0/0**.
