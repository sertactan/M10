# Phase19 — Alpha Vantage historical-listing source staging (2024–2025)

Status: **research CSV collector**, not a PIT identity certificate and not an M10 production database import.

## Motivation

An actual single-date API test on 2026-10-09 returned **6,047** filtered stock listings for **2024-01-31**, broken down as **NASDAQ 3,460; NYSE 2,533; AMEX 54**. These values are *operator-observed*, not embedded in tests or fabricated data. The actual Windows SQLite had **zero** of the 21 requested months, but the SEC financial table already held **12,313,284** facts: do not redownload/replace SEC.

The existing `sync_free_pit_universe.py` writes to `security_master` after matching ticker + exchange. Without a contemporaneous CIK/FIGI, reused tickers can map to the wrong issuer. Therefore stage source files **away from the production SQLite database** until historical identity and delistings can be reconciled with SEC.

## Run from Windows M10

1. Finish any active SEC importer and take/retain the existing local database backup before later production changes. This staging command **does not need to back up or modify SQLite**.
2. From the existing `E:\M10` checkout after reviewing and updating the source:
   ```powershell
   cd E:\M10
   .\.venv\Scripts\python.exe -m scripts.phase19_alpha_pit_staging --start 2024-01-01 --end 2025-09-30
   ```
   No network; list 21 target month-end dates, current local staged files and blockers. M10 loads the local gitignored `.env` without ever printing its `ALPHAVANTAGE_API_KEY`.
3. Run a **single** free Alpha Vantage historical request:
   ```powershell
   .\.venv\Scripts\python.exe -m scripts.phase19_alpha_pit_staging --start 2024-01-01 --end 2025-09-30 --max-requests 1 --execute
   ```
   It stores the original CSV and SHA-256 manifest under the PRIVATE Windows path
   `%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase19\pit_staging`.
   It does not touch `operational.db` or `data/runtime/parquet`.
4. Check the results. Repeating **the same command** verifies existing files and requests the next missing month. Respect the free provider's daily and account-wide rate limits; `--max-requests 1` is the conservative default. No automated scheduling.
5. Keep outputs private and out of GitHub. **Never commit raw CSVs, API keys, .env or licensed market data**. If transferring, check license first.

## Invariants and deferred tasks

- Only a `--execute` run contacts Alpha Vantage, using at most 1 request by default, 5 maximum. Never calls Massive, any paid API, or SEC.
- A CSV with an unpaired manifest, changed SHA-256, different date or invalid source schema blocks with no silent overwrite.
- The current API response is a **retroactive research reconstruction**; a response collected in 2026 is not an original historical market-data file created in 2024. An historical-listed stock's ticker is not stable issuer identity.
- `qualified_stock_rows` is a filtered stock-listing count, *not the number of canonically testable stocks*; no claim of delisting payoffs, accepted_at, PIT identity or adjusted prices.
- Next after the 21-month source gathering: separate CIK/FIGI identity audit (including reused ticker/delisted), annual/quarter SEC as-of evidence audit, authoritative adjusted price provider checks and only then guarded population of historical snapshot tables in the live DB.
- Existing S15.3 and S16 canonical models, WF9 and Learning V3 remain unchanged.
