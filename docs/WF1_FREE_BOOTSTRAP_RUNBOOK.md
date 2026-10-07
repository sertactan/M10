# WF1 Free Bootstrap Runbook

WF1 now has a resumable zero-paid-API bootstrap path.

## Required local configuration

```text
SEC_USER_AGENT=Your Name your-email@example.com
ALPHAVANTAGE_API_KEY=<free key>
```

No paid API credential is required by the WF1 bootstrap.

## One-command baseline

```powershell
python scripts/bootstrap_wf1_free_data.py --start 2013-01-01 --end 2024-12-31
```

Stages:

1. Alpha Vantage dated active-listing PIT snapshots (month-end, resumable).
2. SEC exact-normalized-name unique CIK enrichment for unresolved historical rows.
3. Official SEC Company Facts bulk import for all known US securities with CIKs,
   including inactive/historical rows.
4. Stooq bulk raw-price import for all known tickers.
5. Per-snapshot readiness audit.

## Critical price distinction

Stooq rows are kept as `RAW_ONLY / SCANNER_BOOTSTRAP`. They improve discovery
and raw feature coverage but **do not** satisfy canonical adjusted-price
walk-forward readiness.

Walk-forward price readiness counts only selections whose purpose is:

```text
BACKTEST
BACKTEST_ADJUSTED
```

Therefore a free bootstrap cannot silently convert raw historical prices into a
canonical FM252 outcome series.

## Resume behavior

Alpha Vantage free-plan rate limits may stop the universe stage. Completed
snapshot dates remain stored. Re-run the same command; populated dates are
skipped unless `--overwrite-universe` is used.

The command preserves a nonzero exit code when the PIT-universe stage stops
early, even though later stages and the readiness audit still run.

## Evidence policy

- Current-universe substitution for historical membership: forbidden.
- Ambiguous SEC name-to-CIK match: skipped.
- Stooq RAW_ONLY -> adjusted backtest authority: forbidden.
- Missing V1.4.1 input -> N/A / blocker, never zero.
