# Phase14 — Automatic Daily Alpha Vantage Historical PIT Listings

**Engineering:** Implemented and awaiting CI. **Windows installation:** owner opt-in required.

The automation collects monthly historical US exchange listing memberships for
2013-01 through 2024-12 using the local authorized Alpha Vantage key. It
skips existing monthly records without overwriting them, stops on vendor
errors or quota limits, and limits its own usage to 20 API requests per UTC
day (5 below the advertised free allowance). Other applications and manual
calls to the same key are NOT counted by its ledger; the provider can still
deny a request. No multi-key quota evasion is used.

An exclusive lock prevents concurrent runs. A persistent private daily
request budget and status report survive process restarts:

    %LOCALAPPDATA%\S153ResearchTerminal\runtime\data\runtime\pit_daily_sync\

Reports: latest_status.json and history.jsonl. No API keys, raw listing
rows, or provider error payloads are printed. A crash leaving daily.lock
requires manual inspection of the PID, not automatic lock deletion.

## One-time installation on the Windows M10 computer

Open 64-bit Windows PowerShell (not PowerShell x86). From the checkout:

    cd E:\M10
    git pull
    $env:S153_RUNTIME_ROOT="$env:LOCALAPPDATA\S153ResearchTerminal\runtime"

Dry run — verifies real DB and scheduler settings but creates no task:

    powershell -ExecutionPolicy Bypass -File .\scripts\register_phase14_pit_task.ps1 -DailyAt "09:30"

**Explicit registration** after reviewing the dry run:

    powershell -ExecutionPolicy Bypass -File .\scripts\register_phase14_pit_task.ps1 -DailyAt "09:30" -Register

09:30 is only an example; choose your Windows computer's local time.
The job runs only while the owner is logged on and the PC is switched on;
missed scheduled launches are set to start when available. Windows Task
Scheduler does not work when this PC is off. Avoid same-day manual API
runs if the provider has already hit a free quota.

## Check progress (NO API calls)

    Get-ScheduledTask -TaskName "Meridyen PIT Universe Daily"
    Get-ScheduledTaskInfo -TaskName "Meridyen PIT Universe Daily"
    powershell -ExecutionPolicy Bypass -File .\scripts\run_phase14_daily_pit.ps1 -RuntimeRoot "$env:S153_RUNTIME_ROOT" -StatusOnly

Completion status COMPLETE_LISTINGS_NOT_PIT_CERTIFIED means all 144 month
end listing dates are present, **not** fully verified PIT, adjusted prices,
delisting payouts, SEC filing as-of correctness, WF9 activation, or 10X
model performance. These are separate Phase14 verification tasks.

## Disable or remove

    Disable-ScheduledTask -TaskName "Meridyen PIT Universe Daily"
    Enable-ScheduledTask -TaskName "Meridyen PIT Universe Daily"

To remove, confirm the task identity, then:

    Unregister-ScheduledTask -TaskName "Meridyen PIT Universe Daily" -Confirm

User database and private report stay on Windows. Google Drive remains
optional encrypted backup, never the live operational SQLite database.

## Lightweight daily PIT startup and local progress (2026-10-08)

The daily scheduler no longer calls the full desktop `AppContainer.initialize()`.
That call performed two whole-database `PRAGMA quick_check` passes and
bundled-seed/migration checks even when the sole purpose was a handful of
Alpha Vantage listing snapshots. This is prohibitively slow once the user's
SEC-financial database reaches 8.57 GB.

The optimized daily path:

1. Refuses a missing/renamed operational.db. Uses SQLite `mode=rw`,
   a 10-second lock timeout, required schema/table-column probes, and
   foreign-key enforcement. It never creates a new empty database.
2. Loads the configured local .env without printing secrets; skips
   full SQLite quick_check, migrations and seed imports for this *scheduled
   daily task only*. Separate backups and integrity maintenance remain required.
3. Preserves the exclusive lock and per-UTC-day API budget reservation **before
   provider requests**. Never bypasses provider limits.
4. Writes `latest_progress.json` atomically at stages BOOTSTRAP,
   EXISTING_DB_CONNECTED, CHECKING_MONTH, API_REQUEST_RESERVED,
   SNAPSHOT_STORED, FINAL_COUNTING, and FINISHED. Normal Python exceptions
   record FAILED with the exception class only. Windows forced termination
   can leave the last progress stage and daily.lock; never remove either
   until verifying both owner PID and Task Scheduler state.
5. Writes the existing `latest_status.json` only for a completed run.
   Progress is not a completed backtest, market PIT certification, or
   evidence of API success.

**Safe deployment on Windows**: Do not run git pull or reschedule the
existing process as a live fix. First allow it to finish (or determine
with the operator whether it has stalled), inspect its PID and existing
daily.lock. Then with the task not running, update E:\M10 source and let
the *next* scheduled 20:30 run use this optimized entrypoint. Do not
copy/commit the local operational.db, backup, quota ledger, keys or reports
to the public repository.

For read-only diagnostics while the scheduled task is active:

    Get-ScheduledTask -TaskName "Meridyen PIT Universe Daily" |
      Select-Object TaskName,State
    Get-Content "$env:LOCALAPPDATA\S153ResearchTerminal\runtime\data\runtime\pit_daily_sync\latest_progress.json" -ErrorAction SilentlyContinue
    Get-Content "$env:LOCALAPPDATA\S153ResearchTerminal\runtime\data\runtime\pit_daily_sync\latest_status.json" -ErrorAction SilentlyContinue

