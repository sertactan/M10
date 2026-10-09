# Phase21 — SimFin FREE US daily prices: local, offline coverage audit

Status: code and offline fixtures only. **No real SimFin dataset has been supplied,
downloaded, read or certified by this GitHub task.**

## Why SimFin over unrestricted Stooq requests?

The M10 Windows audit on 2026-10-09 counted **683** local Parquet price
rows in 2024-01-01–2025-09-30 (INOD/MASSIVE 245; CRMD/YAHOO_COMPAT 438).
There were 6 physical Parquet files, 0 canonical BACKTEST_ADJUSTED
selections, and 0 rows in SQLite price_daily.

SimFin currently advertises a **$0 FREE plan**, 5 years of **delayed** bulk
CSV data and daily stock prices including adjusted close. This is a potential
large source, **not a guarantee** that 2024–2025, 6,839 listing keys,
corporate-action-adjusted history, delisted outcomes or correct PIT
availability can be covered.
Official plan page: https://www.simfin.com/en/prices/

Stooq currently has scripted-access/CAPTCHA challenges and terms limiting
redistribution and commercial use. Do **not** bypass CAPTCHAs or automate
thousands of Stooq downloads against access restrictions. Existing
`StooqPriceProvider` remains available as RAW_ONLY for permitted personal
research. Source restrictions apply to stored data; never commit it to public
GitHub.

## Safe Windows workflow

1. If appropriate for your private research, register for a **free** SimFin
   account (no billing) and use its own bulk-download interface to obtain the
   **U.S. daily share prices**, not a fundamentals/derived ratios file.
   Note the account's usage and retention terms. Do not activate a paid
   subscription. Download the CSV or ZIP **privately on Windows**.
2. Update M10 code:

       cd E:\M10
       git pull --ff-only

3. Audit the exact file you actually downloaded (change path):

       .\.venv\Scripts\python.exe -m scripts.phase21_simfin_price_source_audit --input "C:\Users\serta\Downloads\ACTUAL_SIMFIN_SHAREPRICES_FILE.zip"

   A plain .csv path is also accepted. If the ZIP has more than one CSV
   member, the tool blocks; choose the single authentic daily price dataset
   without modifying the original. Do not rename fundamentals as shareprices.

The audit:
- confirms all saved Phase19 PIT listing source hashes for the same 21 months;
- streams the file without reading it all into memory, supports semicolon
  (SimFin default) and comma separators, and reads ZIP without extracting;
- checks OHLC plausibility, eligible window dates, presence of
  a real numeric adjusted close, SimFinId multiplicity, and ticker-only
  intersection with the distinct Phase19 historical tickers;
- stores a **private JSON report**, by default at
  %LOCALAPPDATA%\S153ResearchTerminal\runtime\phase21\simfin_free_price_source_audit.json;
- performs **zero** external/network requests and **zero** writes to
  operational.db, canonical_price_selection, SEC facts, PIT tables or
  Parquet. It does not train any model.
- never treats a matching ticker or SimFinId alone as a verified CIK link.
  Source adjusted-close values still require split/dividend methodology and
  trading-date tests before being canonical.

## After actual audit

Use genuine report counts to decide whether the free bulk covers enough
U.S. equities; a site marketing claim of 5,000 stocks is not evidence of
verified overlap with historical listed/defunct stocks.

Then, in a **separate reviewed step**:
1. map SimFinId / ticker-date to historical security CIK/share class (consider
   alias/reuse; historical availability);
2. verify adjustment method, splits, dividends, delisting returns, source
   gaps, cross-vendor closes and license constraints;
3. implement a segregated validated import and eventual
   BACKTEST_ADJUSTED selection only for independently certified securities.
4. run walk-forward OOS tests then experiment with Learning V3;
   do not alter canonical S15.3/S16 formulae.
