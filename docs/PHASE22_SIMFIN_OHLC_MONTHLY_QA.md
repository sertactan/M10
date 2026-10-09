# Phase22 — SimFin FREE price data quality & monthly historical ticker overlap

**Scope:** fully offline, read-only diagnostics; no data correction, new downloads,
API calls, SEC updates, canonical price selections or model training.

## Evidence reported by operator on 2026-10-09

21 historic listing months verified (2024-01-01 to 2025-09-30),
6,831 historical distinct ticker **strings**, 6,839 ticker+exchange keys.
SimFin US daily share-prices private CSV supplied from FREE bulk download:
- 6,216,939 source price rows
- 2,139,602 rows in requested window
- 2,110,654 pass Phase21 strict OHLC check; 28,948 fail
- 5,307 price tickers in window; 4,242 share ticker string with monthly PIT sources,
  2,589 PIT ticker strings have no price row match in the date window
- source adjusted-close column present, 2,110,622 positive numeric adjusted
  closes among valid OHLC, 32 missing/invalid adjusted close
- 0 source ticker strings with >1 SimFinId **within the window**
- **These are research-only ticker-string overlaps, not canonical historical
  CIK/share-class or true trading date valid matches.**

## How to run

First update:

    cd E:\M10
    git pull --ff-only

Then in PowerShell:

    $file = "$env:USERPROFILE\Downloads\us-shareprices-daily\us-shareprices-daily.csv"
    .\.venv\Scripts\python.exe -m scripts.phase22_simfin_ohlc_monthly_qa --input "$file"

Inputs: original SimFin US shareprices CSV (read-only), existing Phase19
SHA-verified month-end lists, previously generated Phase21 audit JSON.
Phase22 verifies the source SHA against the Phase21 result and independently
recalculates exact total/window/valid/invalid OHLC counts. This fail-closed
reconciliation prevents a silently changed or mistaken input file.

Output stays on the user's private Windows filesystem by default:
`%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase22\simfin_ohlc_monthly_coverage.json`.

Metrics:
- strict OHLC anomaly **reason** counts (open or close outside high/low,
  impossible high/low, nonpositive, non-finite, non-numeric);
- per calendar month number of source tickers with valid pricing and matching
  symbols from *that month's retrospective month-end* listing data;
- number of PIT ticker strings with >=100 and >=300 valid OHLC trading rows
  in (a) any source month and (b) calendar months whose month-end listing
  contains that ticker;
- valid OHLC rows with positive adjusted close and same-month PIT ticker;
- small ticker+date samples; no raw OHLC data redistribution.

**IMPORTANT:** A ticker in a month-end list is not a daily as-of security
identity. A 2024 historical listing queried in 2026 is also not original
2024 availability evidence. Ticker reuse, exchange changes, delisting cash
flows, split/total-return factors and timestamped SEC features require
separate independent certification. An OHLC strict-failure is a
**diagnostic**: do not delete those 28,948 rows or infer SimFin is
incorrect without original provider field semantics and independent
cross-checks. Never treat a source adjusted close as proven canonical.

No production database or model files are written.
