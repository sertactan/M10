# Phase25R — Real 21-month staging source audit and issuer-identity collision quarantine

Input: Private Windows Phase25Q versioned staging SQLite, independent SQLite backup and original monthly Alpha Vantage source files (21 SHA256-backed manifests), plus the original Phase25b qualified-depth report.

Observed Windows results (2026-10-10):

| Observation | Source-confirmed count |
| --- | ---: |
| Month-end US common-stock membership keys (month, ticker, exchange) | 128,088 |
| All valid SimFin price observations Jan2024-Sep2025 | 2,110,622 |
| Qualified source price observations independently reconciled against all 3,557 strong candidates | 1,557,903 |
| Duplicate month+exchange+ticker source records | 485 |
| Of those, differing issuer name or IPO date | **464** |
| Identical duplicates | 21 |
| Unique ambiguous issuer ticker strings | 30 |
| Strong cohort tickers affected | **7** |

The 7 strong-cohort ticker strings needing quarantine: **B, CWBC, FUN, STRR, TEL, TTE, VIVO**. For example in the SAME claimed 2024-01-31 NYSE snapshot the source contains both Barrick Gold Corp and Barnes Group Inc under ticker `B`— ticker-only month-end membership does NOT identify the correct issuer. These data points **must not be certified or scored** pending official dated ticker-to-issuer+class resolution. The original Phase25Q staging intentionally keeps first duplicate row only (with per-source count difference preserved); the Phase25R immutable audit retains the full conflict list with both names and IPO dates.

The historical month-end files were obtained RETROACTIVELY in October 2026, so their dates are not genuine contemporaneously observed issuer identities. The 3,557 cohort is survivorship-skewed; even the 3,550 ticker strings without this specific conflict are **not certified clean**. Stock splits, corporate actions, delisted return, SEC public available_at and daily session calendars remain independently unproven.

## Run

Run from the version-controlled code worktree (not live Hermes branch):

```powershell
$code = "$env:LOCALAPPDATA\S153ResearchTerminal\runtime\phase25r\code_checkout"
Set-Location $code
$manifest = "$env:LOCALAPPDATA\S153ResearchTerminal\runtime\phase25q\staged_datasets\research_pit_28323984fb4f48b1\manifest.json"
& "E:\M10\.venv\Scripts\python.exe" -m scripts.phase25r_real_staging_coverage_qa --manifest $manifest
```

Output: `%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase25r\staging_readonly_reconciliation.json`. The audit is read-only for all source/DB data and verifies both staging and backup `PRAGMA quick_check` and exact 3,557 strong cohort record counts against Phase25b.

**Nothing is automatically promoted:** 0 historical issuer CIK certified by this tool, 0 adjusted price certified, 0 executable WF9, 0 Learning V3.

Next steps: find official historical exchange identities for the ambiguous 30 tickers, verify issuer share-class and delistings, and independently certify authoritative corporate-action price adjustments before promoting even a small cohort.
