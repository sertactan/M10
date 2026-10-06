# S16 Phase 2 — Real PIT Matched-Control Backtest

Status: implementation complete; runtime data population is fail-closed.

## Objective

Turn the 31-event seed set into a reproducible matched case-control benchmark:

- 31 positive seed events
- 50 contemporaneous controls per event
- 1,550 controls total
- V0.2 vs V0.3 ARMED/IGNITION comparison
- 3x / 5x / 10x high and close labels over the next five sessions

## Methodology correction

The 31 historical examples use heterogeneous move definitions. The dataset now
separates:

1. STRICT_PRIOR_CLOSE_TO_5D_HIGH
2. INTRADAY_ONLY_NOT_STRICT_5D_PRIOR_CLOSE
3. IPO_FIRST_TRADE_ANCHOR

A low-to-high intraday 10x is not silently relabeled as a prior-close 5-session
10x. IPO-offer-price moves are kept in the IPO route.

## Event anchor resolution

scripts/resolve_s16_event_anchors.py reads the local PIT price store and resolves
the event month deterministically. Secondary-market events are searched for the
earliest prior-close anchor whose next five sessions reach 10x on adjusted high.
Intraday-only events and IPOs remain separately tagged.

## Candidate snapshot materialization

scripts/materialize_s16_pit_match_candidates.py builds same-date candidates from
the local US common-stock universe using:

- single-provider adjusted price history
- price
- average volume 20
- realized log-return volatility 20
- momentum 5
- momentum 20
- PIT shares outstanding from canonical fundamentals
- market cap = price x PIT shares
- sector / industry when available
- listing age

The broad materializer uses PIT shares outstanding as an explicit proxy for free
float. It writes supply_kind=PIT_SHARES_OUTSTANDING_PROXY and
source_quality=PIT_PROXY. No proxy is presented as exact free float.

For higher-quality enrichment, data/providers/massive_pit_reference.py supports
dated Massive ticker details (market cap, weighted/share-class shares, SIC).

## Matched controls

core/historical/s16_controls.py:

- excludes the positive security itself
- requires the exact same as-of date
- separates IPO and secondary-market pools
- requires common stock
- uses no forward return in matching
- renormalizes sector weight away when sector evidence is missing
- keeps supply/source quality metadata

The existing 31x50 selector remains deterministic.

## S16 feature coverage

core/historical/s16_feature_coverage.py requires all canonical V0.2/V0.3 input
features before scoring. Missing historical social/short/catalyst evidence is not
silently converted to zero.

This protects the false-positive experiment from a common error:

    missing historical evidence != negative signal

## Benchmark interpretation

core/backtest/s16_benchmark.py and
scripts/run_s16_case_control_benchmark.py report threshold grids for:

- V0.2 ARMED
- V0.2 IGNITION
- V0.3 ARMED
- V0.3 IGNITION

against:

- 3x HIGH / CLOSE
- 5x HIGH / CLOSE
- 10x HIGH / CLOSE

Metrics include TP, FP, TN, FN, recall, FPR, specificity, balanced accuracy and
case-control precision.

IMPORTANT: case-control precision is not a real-world probability. The 1:50
negative ratio is chosen by design. Real P(10x) calibration requires an unbiased
whole-market walk-forward prevalence test.

## Current runtime blockers

The Git repository intentionally does not contain the user's local historical
SQLite/Parquet runtime database. Therefore the committed 1,550-slot manifest
cannot be populated in GitHub CI without external historical data.

Canonical V0.2/V0.3 scoring additionally requires PIT sources for all feature
families. Price/SEC-derived features can be reconstructed locally; historical
short interest and historical social attention need dedicated archives/providers.

The system now fails closed until those rows are real and complete.

## Execution order on a populated runtime

1. Resolve the 31 event anchors.
2. Materialize candidate snapshots for every resolved as-of date.
3. Select exactly 50 controls per positive.
4. Materialize S16 feature snapshots strictly as-of each date.
5. Score V0.2 and V0.3 before joining future labels.
6. Compute five-session HIGH/CLOSE outcomes.
7. Join outcomes only after scoring.
8. Run the case-control benchmark.
9. Compare V0.2 vs V0.3 primarily on recall and FPR.
10. Only after this, run unbiased whole-market walk-forward calibration.
