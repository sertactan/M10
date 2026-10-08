# Phase 14 — Historical US PIT Data Integrity and WF9 Activation Gate

**Stage:** PHASE14_CODE_INTEGRATION (2026-10-08)  
**Production:** BLOCKED_REAL_DATA_AND_RUNTIME_UNAVAILABLE  
**Window:** 2013-01-01–2024-12-31 = 144 monthly snapshots.

This phase extends existing M10 WF1/Phase2/Phase3/WF9 and Phase13. It is **not** a
claim that a full, licensed CRSP-quality U.S. market database was downloaded,
that delisted stock payoffs are fully sourced, or that WF9 ever reached
`COMPLETE_AND_ACTIVATED`. Only the Windows host containing the actual
`operational.db` and matching Parquet partitions can establish readiness.

## Improvements in this PR

1. **MarketParquet price integrity:** earlier code copied vendor `close` to
   `adjusted_close` and marked it authoritative `ADJUSTED_ONLY` without
   adjustment evidence. It now requires an explicit `adjusted_close`,
   `adj_close`, `adj close`, `adj. close`, or `close_adjusted` column
   before a series qualifies for `BACKTEST_ADJUSTED`. Raw-only observations
   stay `RAW_ONLY` and cannot be canonical; invalid prices and duplicate
   ticker-date bars are rejected. Vendor adjusted-close claims are still **not
   independently audited**. Existing canonical selections derived from
   legacy raw-only inputs **must be rebuilt and their source verified**.
2. **Dataset audit:** `scripts/phase14_dataset_audit.py` checks all requested
   month-end PIT snapshot dates, their historical source types, monthly price/
   fundamental/feature/S15 V1.4.1 upstream coverage and whether underlying
   Parquet *year partitions* actually exist. No database modification or feed
   usage. Reports `PREFLIGHT_INPUT_COVERAGE_ASSERTED_NOT_PIT_CERTIFIED` only
   if *all* these bounded checks pass, otherwise `BLOCKED`.
3. **Windows activation gate:** `scripts/phase13_windows_pipeline.ps1` now
   requires BOTH native Phase13 readiness and Phase14 physical/source checks
   before its optional `-Execute` native WF9 activation attempt. It refuses
   production when physical partitions are missing or verification was
   truncated. A passing check still requires native WF9 verification.
4. **GitHub-hosted probe:** CI artifacts show missing DB honestly; the
   ephemeral GitHub runner **cannot inspect the user's Windows M10 runtime**.
5. **Tests:** raw-only price rejection, explicit adjusted price acceptance,
   bad/duplicate bars, missing DB/snapshots/Parquet files and bounded-audit
   fail-closed behavior.

## Run on the computer containing real M10 data

From the repository checkout, PowerShell:

```powershell
# Pure read-only diagnostics:
python scripts/phase14_dataset_audit.py --db data/runtime/operational.db --parquet-root data/runtime/parquet --start 2013-01-01 --end 2024-12-31 --price-checks 500000 --out data/runtime/PHASE14_DATASET_AUDIT.json

# Default Windows driver also emits Phase13/Phase14 checks, no activation:
powershell -ExecutionPolicy Bypass -File scripts/phase13_windows_pipeline.ps1
```

When the Windows build uses a custom runtime, set
`S153_RUNTIME_ROOT` to that writable directory. The Python audit's
`--db` and `--parquet-root` should both point to that SAME
runtime; do not point only one at a different installation.

## Controlled data bootstrap — requires data-provider access

Available code:
- `scripts/sync_free_pit_universe.py`: historical listings via Alpha Vantage
  `LISTING_STATUS` or Massive PIT endpoint, if API key and provider entitlement
  permit. Do not infer exact historical PIT support solely from a key.
- `scripts/bootstrap_wf1_free_data.py`: official SEC Companyfacts ingestion
  and Stooq RAW_ONLY histories. Stooq does not become adjusted backtest authority.
- `scripts/bootstrap_wf9_canonical_data.py`: source-selected adjusted price
  ingestion using Massive, MarketParquet (explicit adjustment field), or
  SimFin (adjusted field present); never force Yahoo/STOOQ as authoritative.

A possible workflow, after provider license/coverage verification:

```powershell
python scripts/wf9_environment_probe.py
python scripts/sync_free_pit_universe.py --start 2013-01-01 --end 2024-12-31 --provider AUTO
python scripts/bootstrap_wf1_free_data.py --start 2013-01-01 --end 2024-12-31 --skip-universe
python scripts/bootstrap_wf9_canonical_data.py --start 2013-01-01 --end 2024-12-31 --provider AUTO --concurrency 2
powershell -ExecutionPolicy Bypass -File scripts/phase13_windows_pipeline.ps1
# ONLY AFTER all checks pass, operator explicitly:
powershell -ExecutionPolicy Bypass -File scripts/phase13_windows_pipeline.ps1 -Execute
```

Do not run `--overwrite` or redo canonical selections against arbitrary
historical imports without retaining a complete evidence chain. Inspect actual
CLI help/provider permissions before provider access.

## Remaining gaps before Phase14 can be declared production complete

- Complete 144 point-in-time historical exchange membership snapshots with
  delisted securities and stable security identity. Ticker reuse/changes need
  historical mapping; a 2026 screener is not a historical universe.
- Canonical adjusted OHLCV series, corporate actions and delisting terminal
  proceeds with source license/provenance; yearly Parquet partition presence
  alone does not verify every daily bar, split or the terminal payout.
- SEC facts with filing **available_at**, historical model feature materialization
  and adequate universe-specific coverage. Some listed securities will lack
  standard SEC filings; never fabricate missing issuer facts.
- Independent PIT / survivorship review plus actual WF9 evidence from the
  real runtime; then OOS and false-positive model testing. A code PR or
  aggregated ready percentage is not verified market performance.
- Configured and RESTORE-tested encrypted Google Drive backups: storage
  folders exist but no local runtime credentialed transfer has been proven.

**Operational rule:** Never mark WF9 `COMPLETE_AND_ACTIVATED` from
`PREFLIGHT_INPUT_COVERAGE_ASSERTED_NOT_PIT_CERTIFIED` alone.


## SEC future-period anomaly guard (2026-10-08)

Independent of the Windows PIT scheduler and SEC data import, the
`FundamentalRepository.source_facts_as_of()` query now requires
`period_end <= date(as_of in UTC)` as well as `available_at <= as_of`.
This prevents a Companyfacts period ending in **2039** but carrying a
2026-or-earlier availability timestamp from leaking into the 2013-2024
historical fundamental snapshots. The source/archive rows are not
modified and no canonical formula, scoring weight or gate changes.
Forward estimates and guidance remain in their own separate APIs.

To inspect such outlier facts on the **verified local SEC backup**
with zero data writes, run:

```powershell
cd E:\M10
.\.venv\Scripts\python.exe -m scripts.phase14_sec_temporal_outlier_audit `
  --db "E:\Meridyen_Backups\operational_SEC_20261008_203207.db" `
  --as-of 2026-10-08 --limit 1000 `
  --out "E:\Meridyen_Backups\sec_temporal_outliers_20261008.json"
```

The audit is bounded by *matching rows*, not a random sample of all facts.
It does not prove complete SEC coverage or source acceptance timestamps.
A future-dated fact may require issuer-source review, not deletion.
The read-only audit must never claim WF9 activation. This can run while
PIT downloads progress because it accesses the independent backup.
