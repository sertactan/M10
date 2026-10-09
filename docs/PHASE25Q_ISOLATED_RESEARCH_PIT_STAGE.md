# Phase25Q — 21-month isolated, versioned **research** staging (not canonical)

Goal: Jan 1 2024 through Sep 30 2025 maximal **source-observed** U.S. common stock universe, without altering the production M10 operating database or the original licensed SimFin file. Code only is committed to GitHub; all downloaded vendor files and staging databases remain **private on Windows**.

The source coverage deliberately extends BEYOND the 3,557 best-covered research candidates. The staging loader reads and validates **all 21 historical month-end Alpha Vantage common-stock snapshot files** and streams every valid window price record from the local SimFin CSV (including tickers absent from a same-month listing, tagged appropriately). This supports detecting gaps, censored or disappearing securities, and identity ambiguity rather than silently discarding them. Source data are not canonical trades or model features.

## Input requirements and fail-closed provenance

- Monthly snapshots: `%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase19\pit_staging\YYYY-MM-DD.csv`, plus each SHA256-verified `.manifest.json` (21 months).
- Original unchanged user's `%USERPROFILE%\Downloads\us-shareprices-daily\us-shareprices-daily.csv` verified against Phase24 `source_sha256`.
- Phase24 5,307 source SimFinId candidate mappings (present-day issuer CIK **not historical PIT proof**).
- Phase25k 133 research-stage fail-closed candidate gate rows.
- Existing operational SQLite is referenced as an **external, read-only SEC fact source** but not copied or modified.

### Staging caveat that MUST NOT be waived

**Every Alpha Vantage monthly historical listing snapshot was retrieved retroactively in October 2026, AFTER its nominal historical date.** The manifest's actual `retrieved_utc` is stored. No backdated `available_at` is invented. Month-end listing is never automatically treated as daily membership **before** that month-end. Similarly, SimFin `Adj. Close` is a possibly retrospectively revised vendor series, not contemporaneously known adjusted price. We capture source price as-is but every stored row has `source_adjustment_certified=0` and `historical_security_identity_certified=0`.

Membership records preserve the original historical as-of month-end and exchange; source price records preserve `SimFinId`, ticker, original daily OHLC, vendor adjusted close, volume, vendor dividend column (uncertified), and same-month listing overlap. No cash/split or delisting return is imputed.

## Windows invocation

Run from a fresh branch's separate worktree containing this script. DO NOT switch the live Hermes development branch and DO NOT import into production SQLite.

```powershell
$code = "$env:LOCALAPPDATA\S153ResearchTerminal\runtime\phase25q\code_checkout"
Set-Location $code
$file = "$env:USERPROFILE\Downloads\us-shareprices-daily\us-shareprices-daily.csv"
& "E:\M10\.venv\Scripts\python.exe" -m scripts.phase25q_isolated_source_pit_stage --input $file
```

Output: `%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase25q\staged_datasets\research_pit_<version>\research_pit.sqlite`, immutable manifest `manifest.json`, and independent `research_pit.backup.sqlite` verified by SQLite quick_check. The version ID is derived from SHA256 of every source CSV and schema. A rebuild with the same sources first verifies and **reuses** the existing stage; it will not overwrite. An interrupted `.building` folder is deliberately NOT auto-removed because no user's original files should ever be deleted without inspection; the stage may be resumed only with controlled operator review.

To rollback use only this **new isolated staged dataset** directory after verifying its resolved path is under `phase25q\staged_datasets`; there is no production mutation to roll back.

## Next release gate (Phase25R–25U)

Review full cohort identity including delisted/time-varying ticker/exchange, exchange session calendars, official split/dividend/spin-off/ADR and terminal outcomes; date-stamped SEC filings' **public dissemination** and feature available_at. Promote **only independently verified** rows using explicit controlled importer and audit trail. Never rely on the best-surviving 21/21-month ticker cohort as a complete market.

Learning V3 requires authoritative point-in-time features, fully matured 252-session labels and chronological OOS folds; WF9 needs canonical adjusted market data and month-level exact PIT universe. Neither will run until those prerequisites pass; no synthetic wins or fabricated S15.3/S16 scores.
