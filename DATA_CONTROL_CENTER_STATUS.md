# Meridyen Data Control Center — Phase 1 (Read Only)

This change adds a DATA CONTROL button to the M10 PySide6 header.
Panel: PIT listing months (target 144), SEC financial fact row count, US
CIK matches, source-isolated price series and adjusted-series flags,
split/dividend source records, pilot versus backtest price selections,
WF5/WF6 run rows, WF8 activation record rows and local PIT scheduler
report status. It NEVER certifies WF9 or model accuracy.

## Safe during SEC Companyfacts import

- NO API calls, no downloads, no SQL writes, no migrations, no bootstrap,
  no model execution. Reads the installed M10 database via SQLite URI mode=ro
  and PRAGMA query_only=ON. No new empty databases are created.
- Manual REFRESH only. Worker runs on Qt global thread pool to keep the
  desktop responsive. On SQLite busy/read error, UI displays a blocked
  diagnostic and users can retry later. No auto-retry loops.
- SEC count and PIT availability are approximate point-in-time diagnostics;
  the importer can still be processing records. Existing facts are not
  independently verified to match original SEC filing acceptance times.
- Historical PIT source counts, adjusted-bar metadata and stored split/
  dividend events are insufficient evidence of survivorship-free WF9,
  delisting cash payout, full trading-calendar history or 10X predictive
  accuracy. WF9 is explicitly marked NOT VERIFIED.

## Use on Windows

Keep the SEC importer alive. Do not launch another import into that DB.
After updating E:\M10 via git pull and restarting a source-based M10 desktop
process, click DATA CONTROL -> REFRESH (READ ONLY).

An existing installed Windows EXE does not receive the new button via
git pull: rebuild/publish the installer after these UI changes merge.
The report is local and does not upload licensed data or secrets to GitHub.

## Remaining work

This is a first, read-only Mission Control panel. Future tasks include
job orchestration, per-stage progress and history, scheduled backups,
deeper data quality drilldowns and production WF9/learning readiness.

## Phase 2 — Data coverage and observed SEC import progress

Faz 2 extends the MANUALLY refreshed and READ-ONLY DATA CONTROL window.

- PIT: annual 2013-2024 month-end coverage (not certified PIT).
- SEC: companyfacts.zip and .part size and timestamp are ARCHIVE metadata.
  A complete zip does NOT prove that the importer has finished.
- SEC facts: row count DELTA between two manual refreshes only. First refresh
  shows FIRST OBSERVATION. A zero change does not prove a stalled job.
- Prices: vendor-flagged adjusted source series, overall min/max dates and
  reported bar totals; no claim of complete historic returns/delistings.
- API providers: persisted circuit states, consecutive failures, and up
  to 5 failure observations among latest 100 provider events. Never show
  original free-form provider messages or sensitive credentials.
- WF9: local cached Phase13 preflight schema/status/timestamp and blockers;
  older than 24 hours marked STALE. Even PREFLIGHT_READY does not mean
  WF9 COMPLETE_AND_ACTIVATED. Missing report means not run/unknown.
- PIT budget: requests reserved by local PIT sync only, not account-wide.
- Background sync: grouped persisted status counts, no payload content.

Safety: SQLite mode=ro, PRAGMA query_only=ON, 750ms timeout,
manual refresh only, no downloads/network, no migrations or SQL writes,
no database bootstrap, no SEC import restart, no auto-polling or trading.
File-based report reads max 200 KB with an exact known schema.
Provider event reads are bounded to last 100 records.

Existing installed Windows EXE is NOT updated just by git pull;
a separate desktop build is necessary. Do not stop the running SEC import
to install UI updates. See tests/test_data_control_center.py.

Phase 3 remains: reliable SEC import checkpoint persistence, detailed
historical evidence diagnostics, exclusive-lock job orchestration,
and independently confirmed WF9 + original PIT acceptance timestamps.
