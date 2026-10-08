# Phase14 — Adjusted Prices, Splits, Dividends, Delisting: Safe Pilot

This pilot is **NOT** an installation of a historical price database, and it
does not certify real PIT, total return, or WF9 readiness. It works with
the actual Windows M10 `operational.db` only after the owner explicitly runs
it. The ChatGPT plugin cannot access the owner's Windows SQLite directly.

## What the current M10 code can and cannot do

- Existing `MassivePriceProvider.get_history` returns **raw and adjusted**
  daily closes when the plan permits the requested dates.
- Existing `MassivePriceProvider.get_splits/get_dividends` extracts vendor
  corporate actions; this new pilot stores those events via
  `PriceRepository.save_splits/save_dividends`. Returns of an empty event
  list are NOT proof that no split or dividend occurred.
- Local `MARKETPARQUET` and `SIMFIN` may supply adjusted prices; a
  **configured Massive account is still required for explicit corporate
  actions** in this pilot. No fake split events inferred from prices.
- Historical delisting effective date, cash-out, bankruptcy/merger treatment,
  exchange identity and total investment return require additional primary
  evidence and are **not** provided by this pilot. They stay
  `NOT_AVAILABLE_UNVERIFIED`. No 10X backtest score is published.
- `PHASE14_ADJUSTED_PILOT_UNVERIFIED` rows are intentionally separated from
  real `BACKTEST_ADJUSTED` selections until audited. The imported price
  partitions are source-isolated Parquet under the installed runtime.

## Before running

1. Close Windows M10 desktop and retain a verified SQLite online backup.
2. Verify the account's historical Massive entitlement. Free account
   recency/history is limited and **may not cover 2013–2024**; Massive's
   splits/dividends endpoint has different history limits from daily bars.
   Neither the Alpha Vantage free listing-status key nor a GPT subscription
   unlocks a 12-year price feed.
3. Configure a legitimately obtained Massive API key in private
   `E:\M10\.env` as `MASSIVE_API_KEY=...` (not PowerShell text; never
   share key in screenshots); OR provide licensed MarketParquet/SimFin files
   via `MARKETPARQUET_ROOT`/`SIMFIN_PRICE_BULK_PATH` in `.env`.
   Massive remains needed for this pilot's explicit split/dividend events.
4. Keep the original PIT scheduler; this pilot is a **separate** one-stock
   research exercise, not a broad market bootstrap.

## Preview: NO NETWORK, NO DATA WRITES

```powershell
cd E:\M10
git pull
$env:S153_RUNTIME_ROOT = "$env:LOCALAPPDATA\S153ResearchTerminal\runtime"
.\.venv\Scripts\python.exe -m scripts.phase14_price_actions_pilot --ticker INOD --start 2013-01-01 --end 2024-12-31 --provider MASSIVE
```

Returns `READ_ONLY_PREVIEW` including boolean provider configuration,
delisting PIT flags. It must **not** create a blank database or retrieve
a real data feed.

## Optional explicit live load — small one-stock pilot

Run **only after** a backup and verified provider access, preferably with
a short historical window to check provider limits:

```powershell
.\.venv\Scripts\python.exe -m scripts.phase14_price_actions_pilot --ticker INOD --start 2023-01-01 --end 2023-12-31 --provider MASSIVE --execute
```

For a local price file with valid adjusted-close columns:
`--provider SIMFIN` or `--provider MARKETPARQUET`, but Massive
corporate action credentials are still required. Preview before execute.

Expected **partial** outcome: `PARTIAL_IMPORTED_DELISTING_AND_PIT_UNVERIFIED`
plus exact `adjusted_price_bars_saved`, `splits_saved` and
`dividends_saved` counts, and file path under the installed runtime.
It explicitly reports `wf9_activated=false`,
`historical_identity_pit_verified=false` and
`delisting_consideration_status=NOT_AVAILABLE_UNVERIFIED`.

Report records are stored in the *private* local
`%LOCALAPPDATA%\S153ResearchTerminal\runtime\data\runtime\phase14_price_actions\`
folder. Never upload real license-restricted data to the public M10 GitHub.

## Next phases

1. Verify source date range, historic ticker/CIK/share class identity.
2. Reconcile split/dividend vendor event pagination, corrections and
   vendor-reported adjustment conventions; distinguish split-adjusted close
   from **dividend total-return** (not equivalent).
3. Acquire authenticated delisting proceeds and terminal event outcomes.
4. Run Phase14 audits, finish 144 PIT month-ends, SEC available_at facts,
   feature coverage, independent forward-outcome and WF9 gates. A pilot
   selection MUST NOT be promoted automatically.

This script does not perform historical delisting cashflow ingestion, automatic
full US stock ingestion, live broker trading or canonical score generation.
