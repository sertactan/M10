# Phase 14 — Safe Preview of WF5/WF6 SQLite Schema

Status: engineering-only schema migration preview. **No production database
migration happens in this script**.

## Why this step is needed

The installed Windows M10 local `operational.db` was reported with
`security_master`, `universe_snapshot_membership`, price and
fundamental tables, but no `wf5_replay_runs` or `wf6_walk_forward_runs`.
It also had **no 2013–2024 PIT month-end snapshots**. Missing WF5/WF6
tables are a *schema problem*; 144 missing month ends are a *data problem*.
The former can be previewed without erasing the live data. Schema migration
does not create true historical market data.

## One command — test on a verified copy, NOT live

Open Windows PowerShell in the checked-out source `E:\M10`:

```powershell
cd E:\M10
git pull
.\.venv\Scripts\python.exe -m scripts.phase14_schema_preview --source-db "$env:LOCALAPPDATA\S153ResearchTerminal\runtime\data\runtime\operational.db" --backup-dir "E:\Meridyen_Backups"
```

Before running, close the Meridyen desktop app if possible to keep the
local operational store quiet; nevertheless, the script uses a consistent
SQLite **online backup**, not `copy` of an open DB or its WAL file.

The script creates **three NEW files** under `E:\Meridyen_Backups`:
1. `operational_pre_schema_....sqlite3`: consistent verified backup of
   the original, hash recorded; not modified by the preview.
2. `phase14_schema_preview_....sqlite3`: a second copy where M10's actual
   `SQLiteStore.initialize(recover_corrupt=False)` runs.
3. `phase14_schema_preview_....json`: separate result with pre/post table
   counts, SQLite checks, and new/missing WF5/WF6 tables.

The original runtime database is opened READ ONLY, never upgraded, deleted,
replaced, or attached for writes. If a schema migration fails, the original
and backup remain untouched and the report says `SCHEMA_PREVIEW_BLOCKED`.
The output is outside the M10 GitHub checkout. Do NOT upload backups or
licensed data to the public repository.

Only after receiving `SCHEMA_PREVIEW_SAFE_ON_COPY_ONLY` and verifying
`preview_integrity=ok`, `pre_existing_rows_preserved=true`,
`missing_required_tables=[]` should the operator contemplate a
**separate**, app-closed, owner-authorized migration of the installed
runtime. This script deliberately has no `--apply` argument.

## Follow-up (NOT automatic)

After the schema is verified, the missing 144 monthly historical PIT
snapshots, canonical adjusted price selections, financial-filing as-of
features, and independent corporate-action/delisting evidence still require
provider-appropriate bootstrap and audits; subsequently WF9 can be
executed only when all safeguards pass. No 10X metrics or model training
may be claimed from installing missing schema tables.

The verification report is safe to share **after checking for sensitive
local paths**; DO NOT share `.sqlite3` or live `.db` files in public
GitHub issues.
