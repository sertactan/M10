# Phase 18 — Local-First Meridyen Database, PIT Intake and Optional Drive Data Vault

Status: ENGINEERING SUBMITTED. Real data and M10 Windows activation remain unverified.

## Decision: Is uploading historical data to Google Drive mandatory?

**NO.** Windows M10 is the operational DB host. The correct layout is:

- SQLite operational database: `S153_RUNTIME_ROOT/data/runtime/operational.db`.
- SQLite Learning V2 journal: `S153_RUNTIME_ROOT/data/runtime/meridyen_learning.sqlite3`.
- DuckDB analytics: `S153_RUNTIME_ROOT/data/runtime/analytics.duckdb` (local files / Parquet scans).
- Partitioned Parquet: `S153_RUNTIME_ROOT/data/runtime/parquet/` (historical prices/features).
- Google Drive 5 TB: optional encrypted offsite backup, raw-file archives where vendor terms allow, backups and immutable experiment results; **NOT** the SQLite/DuckDB live writable mount.
- Public GitHub: code/tests and sanitized documentation only; never export positions, raw licensed vendor datasets, private db or rclone tokens to public Git.

## One command on Windows

From source root:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/phase18_windows_intake.ps1 -ShowReport
```

For installed M10 using another writable root:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/phase18_windows_intake.ps1 -RuntimeRoot "D:\MeridyenData" -ShowReport
```

Or an explicit DB and Parquet directory:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/phase18_windows_intake.ps1 -OperationalDb "D:\MeridyenData\data\runtime\operational.db" -LearningDb "D:\MeridyenData\data\runtime\meridyen_learning.sqlite3" -ParquetRoot "D:\MeridyenData\data\runtime\parquet" -ShowReport
```

Output is PRIVATE/LOCAL: `data/runtime/phase18/activation_report.json` under the selected runtime root. The gitignore excludes these local reports from public commits. The report checks database presence/integrity, required tables, real 144 PIT snapshot dates, adjusted price coverage, physical Parquet inventory, mature learning labels and available M10 source-run statuses.

Missing DB or no 144-date PIT coverage -> blocked. A bounded readiness scan is NOT independent security identity/delisting/filing/as-of data certification. No automatic provider download and no WF9 activation.

## Remaining real-data activation

1. Identify user's actual Windows writable runtime; run Phase18 report. A GitHub runner's empty data files cannot speak for a local installer.
2. Fill 2013–2024 exact historical listing membership, stable CIK/security ID/delisted tickers and corporate-action adjusted price paths using permitted PIT vendors. Run existing `scripts/sync_free_pit_universe.py`, `scripts/bootstrap_wf1_free_data.py` and `scripts/bootstrap_wf9_canonical_data.py` as provider permissions allow. Stooq RAW_ONLY bars are not canonical adjusted prices.
3. Resolve Phase13 and Phase14 blockers; verify independent source provenance then run native WF9 `COMPLETE_AND_ACTIVATED` on Windows. No evidence -> no achievement claim.
4. Complete real WF5 and WF6 runs; ingest 252-session mature labels via `wf5-labels-import`; evaluate Phase15 conditional OOS and Phase17 V3 challenger without automatically promoting any model.
5. Optional backup: use existing Phase16 local SQLite online snapshots. Only on Windows, configure `rclone crypt` to the correct Drive vault and test cloud upload **and** restore. Do not sync active SQLite, DuckDB or files while writers are active.

## Important distinctions

- 5 TB Google Drive capacity is STORAGE, not a transactional database server.
- A Drive desktop-sync directory is not an appropriate active SQLite/DuckDB location.
- Cloud backup is optional for computing and learning, but strongly recommended for disaster recovery.
- Large data storage in Google Drive may be constrained by data-provider licensing and upload bandwidth; archive only permitted files.
- Learning V3 needs actual historically **mature** price outcomes, not 2026 current screener winners or research-only SEC notes.
- The local report is operational evidence only, not a real 10X accuracy measurement.

## Verification gates

CI passing validates code and synthetic fixtures. Actual completion requires a Windows Phase18 report, a complete PIT data evidence chain, WF9 production evidence, nonempty WF5 mature outcomes, and a separate encrypted cloud restore receipt if the owner wants offsite backups.
