# Phase 14 — Guarded Installed-Schema Upgrade (Owner-Opt-In)

## Status and limits

An earlier `scripts.phase14_schema_preview` run on the user's
Windows M10 database returned `SCHEMA_PREVIEW_SAFE_ON_COPY_ONLY`,
`snapshot_integrity=ok`, `preview_integrity=ok`,
`pre_existing_rows_preserved=true`, and no missing required tables.

This **does not** show that the user's live DB has been changed. Phase14
still lacks 144 historical 2013–2024 PIT month-end snapshots and the
adjusted-price/SEC source coverage required for WF9.

## 1. Update M10 and shut down the desktop app

Open standard Windows PowerShell:

```powershell
cd E:\M10
git pull
```

Close the Meridyen desktop app, any background worker, and other scripts
that use the M10 `operational.db`. The migration refuses any existing
`-wal`, `-shm`, or `-journal` file; don't manually delete them.
If you see these files, close the application completely and consult the
owner's existing operational DB recovery workflow instead.

## 2. Repeat a read-only preparation

```powershell
$source = "$env:LOCALAPPDATA\S153ResearchTerminal\runtime\data\runtime\operational.db"
.\.venv\Scripts\python.exe -m scripts.phase14_live_schema_upgrade --source-db "$source" --backup-dir "E:\Meridyen_Backups"
```

Expected status:
`APPLY_READY_REQUIRES_EXPLICIT_OWNER_CONFIRMATION`. The script builds
a **fresh** immutable online snapshot and migration preview, keeping both
outside the public Git checkout. Still NO modifications to the installed
DB. The previous on-copy preview result remains valuable and can be shared
without disclosing private SQLite file contents.

## 3. Optional explicit live schema upgrade (NOT automatic)

Only if the new dry run is green, M10 app/workers are closed and you have
chosen to update the installed DB:

```powershell
$source = "$env:LOCALAPPDATA\S153ResearchTerminal\runtime\data\runtime\operational.db"
.\.venv\Scripts\python.exe -m scripts.phase14_live_schema_upgrade --source-db "$source" --backup-dir "E:\Meridyen_Backups" --apply --confirm-app-closed --confirm-source-exact "$source"
```

This is not a repair for missing historical data; it updates the SQLite
**schema** only. Rechecks source hash and timestamps, refuses WAL/SHM
sidecars, migrates a copy on the same volume as the live SQLite file,
verifies all original table row counts and complete integrity, and then
renames the previous original into a UNIQUE `.pre_phase14-....bak` rollback
file next to the installed DB. The backup in `E:\Meridyen_Backups`
remains untouched.

Success:
`LIVE_SCHEMA_UPGRADED_WITH_ROLLBACK_RETAINED`,
`live_database_modified=true`, `post_migration_integrity=ok`.
Keep the rollback and independent snapshot until the updated app has
successfully read the new schema and historical data imports have been
verified. An installer may have additional application-version constraints;
this code does not update the currently installed EXE.

**Warning:** the on-disk rename is not a global transactional upgrade across
other processes, WAL files, or multiple volumes. Confirm the app is closed.
On Windows, an open SQLite handle may cause a rename to fail. The script
tries to restore the original DB on an interrupted install, and retains the
rollback even after success. It never cleans WAL or overwrites existing
backups.

## 4. Verify real PIT data independently

After a successful installed schema upgrade and app restart, rerun:

```powershell
$env:S153_RUNTIME_ROOT="$env:LOCALAPPDATA\S153ResearchTerminal\runtime"
.\.venv\Scripts\python.exe -m scripts.phase18_storage_readiness --runtime-root "$env:S153_RUNTIME_ROOT" --out "E:\M10\phase14_post_schema.json" --report-only
```

A green schema is NOT `WF9 COMPLETE_AND_ACTIVATED`. The remaining phase
requires valid historical 2013–2024 PIT membership for 144 month ends,
adjusted-price and delisting evidence, as-of SEC fundamentals/features,
and an independently verified native WF9 production run.
