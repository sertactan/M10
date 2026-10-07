# WF1 + WF2 — Free Data / Feature Completion

Status: ACTIVE DEVELOPMENT

## Goal

Build a zero-paid-API evidence layer for S15.3 V1.4.1 walk-forward research
without changing any frozen model formula.

## WF1 — Free historical data layer

Authoritative/free sources already available in the repository:

- SEC EDGAR Company Facts / filings for PIT fundamentals
- Stooq bulk/local Parquet for free historical price bootstrap where eligible
- current SEC universe
- free-key Alpha Vantage LISTING_STATUS historical snapshots for dates after 2010-01-01
- public STOCK_DATA_PIT archive only inside its provider-declared reconstructable interval

### Historical-universe rule

A current symbol list may never be substituted for a historical universe.

For whole-market probability calibration, a date must have an exact PIT
membership snapshot from an evidence-bearing historical source. Price-history
existence may be used for diagnostics/proxy research, but must not be promoted
to `EXACT_PIT` market-prevalence evidence.

The current public STOCK_DATA_PIT artifact has its own reconstructable floor;
the provider enforces that floor before rows are written.

## WF2 — Feature completion

The following categories are separated:

### A. Exact canonical definitions already frozen

Implement whenever evidence exists:

- raw current price / market cap
- revenue / FCF / margins / dilution
- raw per-share series
- destination SupportedMC formulas from S15.3 V1.2
- peer-relative valuation inputs
- V1.4.1 scenario construction from the frozen V1.4.1 spec

### B. Defined concept but missing exact 0–100 normalization

Do not invent scores for:

- F49 MCR
- F50 TAMMC
- F52 RPS
- F53 FPS
- MODEL_FIT where exact mapping is unavailable

Materialize evidence-safe raw inputs instead. Canonical score stays N/A until an
explicit new version freezes the missing mapping.

### C. Cross-sectional/historical inputs

PIR_VAL, XR, H10 and HMG require same-date peer or historical cohorts. They are
not single-security materializer outputs.

## New readiness audit

`core/research/walkforward_readiness.py` measures, per PIT snapshot date:

- universe membership
- exact-PIT status
- canonical price coverage
- PIT fundamental coverage
- materialized feature coverage
- V1.4.1 upstream coverage
- explicit blockers

Run:

```
python scripts/audit_walkforward_readiness.py --all-snapshots
```

This audit never upgrades missing evidence to READY.


## Free historical-universe backfill

With a free Alpha Vantage key in `ALPHAVANTAGE_API_KEY`:

```
python scripts/sync_free_pit_universe.py --start 2013-01-01 --end 2024-12-31
```

The script writes deterministic month-end snapshots, skips already-populated dates,
and stops cleanly on API/rate-limit responses without deleting completed snapshots.
This makes the free workflow resumable while preserving PIT provenance.
