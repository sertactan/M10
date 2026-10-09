# Phase23 — Offline SimFin nonpositive OHLC source diagnostics

**Status:** Tool and synthetic regression tests prepared. Actual user's
SimFin CSV data has NOT been audited by Phase23 until Windows command completes.

## Evidence before Phase23

From the actual **2024-01-01 to 2025-09-30** Windows Phase22 report:
- 21 / 21 historical *research* monthly listing files verified.
- 2,139,602 SimFin shareprice rows within the range.
- 2,110,654 strict OHLC valid rows, 28,948 invalid.
- ALL 28,948 invalid rows classified as `NONPOSITIVE_OHLC`.
- 4,119 ticker strings have 100+ valid OHLC rows during calendar months
  in which they appeared in a retrospective historical month-end listing,
  3,882 have 300+ such rows.
- 1,742,156 monthly ticker-aligned rows pass strict OHLC AND carry positive
  numeric adjusted close. This is a **ticker-string overlap**, NOT a canonical
  PIT identity, verified adjustment factor or model-training authorization.

This phase determines exactly which of Open, High, Low, and Close are
zero/negative in the 28,948 rows. Reasons are not exclusive by column:
one row can have zero Open **and** zero Low. Counts of patterns, unlike
field occurrences, count rows exactly once.

## Run locally, no API, no new files except small private report

```powershell
cd E:\M10
git pull --ff-only

$file = "$env:USERPROFILE\Downloads\us-shareprices-daily\us-shareprices-daily.csv"

.\.venv\Scripts\python.exe -m scripts.phase23_simfin_nonpositive_ohlc_diagnostics --input "$file"
```

The module compares the SHA-256 hash of the original local CSV against
the previously saved Phase22 report and **fail-closes** if they mismatch.
It replays the old exact total and OHLC counts; the 415MB original is
streamed, not fully materialized in RAM. For honest column-level
attribution the original CSV must be scanned once more; previous Phase22
report saved only aggregate reason counts.

Default JSON output:
`%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase23\simfin_nonpositive_ohlc_diagnostics.json`

Read:
- `nonpositive_field_occurrences_not_distinct_rows`:
  per-field zero/negative occurrences
- `exact_nonpositive_field_pattern_rows`: row counts by combined
  pattern, e.g. `OPEN_ZERO+LOW_ZERO`.
- `nonpositive_rows_with_positive_raw_close`, and same with positive
  `Adj. Close`: raw/adjusted close may be present even when high/low
  missing; **no automatic imputation or conversion to canonical**
- `top_tickers_nonpositive_rows_not_security_identity`: candidates
  for manual checking, not a ranking of investable companies.
- `sample_rows_small_private_audit_only`: small diagnostics restricted
  to the Windows local report; keep provider price data off public GitHub.

Never auto-delete, set missing High/Low to Close, override split/dividend
adjustments, or join historical SEC CIKs solely by ticker.

The existing 12,313,284 SEC facts, 21 month CSVs, M10 models, and all
price selections remain untouched. This investigation does not
complete historical identity certification, delisting returns, PIT
adjusted prices, WF9 backtests or Learning V3.
