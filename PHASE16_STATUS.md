# Phase 16 — Learning V2 automatic cycles, local backups and cloud recovery

**Status (2026-10-08): code integration; local/CI synthetic tests only.**
**Real Windows scheduler not registered**; **Google Drive rclone crypt not yet authenticated on M10 Windows**;
**cloud upload and restore not actually executed on the user's Google Drive**.

This is a local-first architecture for the *private* Learning V2 SQLite
evidence database. It does NOT fetch prices, train an ML model, promote an
unreviewed S15/S16 challenger or autonomously modify code.

## Phase 16 features

1. An explicit, one-shot `scripts/phase16_learning_cycle.py` command.
   It optionally imports research bundles, dated backtest JSON and mature
   WF5 labels **only when provided**; aggregates diagnostics, then uses
   SQLite's online-backup API. Atomic `*.cycle.lock` prevents concurrent
   scheduled cycles. If a previous run crashed and left a lock, inspect
   the recorded PID before manually deleting it — never blindly clean it.
2. Each backup has a collision-safe unique filename, a SHA-256 manifest and
   a full SQLite integrity check. The active DB is **never** directly synced.
3. `scripts/sync_learning_backup.py` verifies the local rclone remote
   actually reports `type=crypt` *without logging its sensitive config*.
   It stores BOTH the SQLite snapshot and its manifest under
   `Database_Backups/Encrypted/` within the configured encrypted remote.
   Every upload must download a round-trip copy and verify SHA-256,
   manifest bytes and SQLite integrity before reporting success.
4. Restore to a **new** local SQLite file only, refusing to overwrite an
   existing database. The restore verifies both hash and SQLite structure.
   Cloud disaster recovery can retrieve the manifest **even when every
   local manifest and database file has been lost** (provided the remote
   and encryption credentials still exist).
5. `scripts/register_phase16_task.ps1` builds an explicit daily Task
   Scheduler entry at the user-specified Windows **local time** and is
   DRY RUN by default; `-Register` is required for installation. The
   interactive account must be logged on for the task to run.

## Quick start — M10 Windows source checkout

Replace paths with your **actual writable M10 runtime root**, typically
`$env:S153_RUNTIME_ROOT\data\runtime` if that variable is configured.

```powershell
# Initialise only when you intend to start a fresh learning database:
python scripts/learning_v2.py --db "D:\M10\data\runtime\meridyen_learning.sqlite3" init

# One-off cycle, LOCAL snapshot only, no cloud transfer:
python -m scripts.phase16_learning_cycle --learning-db "D:\M10\data\runtime\meridyen_learning.sqlite3" --backup-dir "D:\M10\data\runtime\learning_backups"

# OPTIONAL — explicitly approved real WF5 source ingestion:
python -m scripts.phase16_learning_cycle --learning-db "D:\M10\data\runtime\meridyen_learning.sqlite3" --backup-dir "D:\M10\data\runtime\learning_backups" --operational-db "D:\M10\data\runtime\operational.db" --wf5-run-id YOUR_COMPLETE_WF5_RUN_ID
```

The WF5 ingestion will fail closed if there are no mature valid labels.
With no new source arguments, the cycle **audits and backs up existing
learning evidence**; it is not constantly mining the market.

## Google Drive (5 TB account) setup

Google Drive capacity is available but needs *rclone authentication and a
separately configured crypt remote on the actual Windows machine*.
The remote's underlying folder should be chosen by the account owner.
This script appends `Database_Backups/Encrypted/` **within** the root of
that crypt remote; avoid accidentally nesting that prefix twice.

Do not commit `rclone.conf`, remote tokens or passwords to this public
repository. **Keep an offline copy of the crypt password/salt**: without
these, encrypted cloud recovery may be impossible.

```powershell
# Configure a normal Google Drive remote, then an rclone "crypt" remote
# layering above the chosen Drive folder:
rclone config

# Inspect upload plan only (NO upload, NO credentials displayed):
python scripts/sync_learning_backup.py --manifest "D:\M10\data\runtime\learning_backups\YOUR_BACKUP.manifest.json" --remote-crypt meridyen_crypt:

# Upload both snapshot and manifest, roundtrip-verify them:
python scripts/sync_learning_backup.py --manifest "D:\M10\data\runtime\learning_backups\YOUR_BACKUP.manifest.json" --remote-crypt meridyen_crypt: --execute --confirm-crypt-remote

# Restore from cloud with just the encrypted-remote manifest filename,
# to a path that does NOT exist yet:
python scripts/sync_learning_backup.py --cloud-manifest-name "YOUR_BACKUP.manifest.json" --remote-crypt meridyen_crypt: --restore-to "D:\M10\recovered_learning.sqlite3" --execute --confirm-crypt-remote
```

**Verify a real cloud restore before calling this production-ready.** The
SHA256 and SQLite checks catch inadvertent corruption, but aren't a digital
signature authenticating the cloud manifest against a malicious replacement.
Keep a signed offline list of original snapshot hashes for adversarial
tamper-detection. rclone crypt protects data at rest only if the owner
actually configures, secures and retains its encryption secrets.

## Optional Windows Task Scheduler registration

Explicitly choose your daily Windows **local** time (example 03:00,
NOT an implicit scheduled action by ChatGPT):

```powershell
# Dry run — prints configuration, makes NO task:
powershell -File scripts/register_phase16_task.ps1 -DailyAt "03:00" -LearningDb "D:\M10\data\runtime\meridyen_learning.sqlite3" -BackupDir "D:\M10\data\runtime\learning_backups"

# Only if you approve daily backups:
powershell -File scripts/register_phase16_task.ps1 -DailyAt "03:00" -LearningDb "D:\M10\data\runtime\meridyen_learning.sqlite3" -BackupDir "D:\M10\data\runtime\learning_backups" -Register
```

Use `-RemoteCrypt meridyen_crypt: -EnableCloud -Register` **only after**
confirming cloud auth, the encrypted remote folder and a successful
end-to-end roundtrip/restore. The scheduler **won't** be installed from
ChatGPT remotely and the task requires an interactive logged-on user.

## Data privacy, evidence and scope limits

- Public GitHub contains source code, synthetic tests and docs **only**.
- Learning journal resides on M10's local writable drive; backups should be
  encrypted and kept outside the repository.
- Research records are **not** trading labels; no canonical model changes.
- Phase14 true 2013–2024 PIT data and a verified WF9 run remain blocked by
  lack of user Windows operational.db and licensed/historically complete
  prices/universe. Phase15 actual market OOS metrics are likewise pending.
- Task registration, live Drive upload and cloud restore **must be tested on
  the user's Windows M10 computer**; CI tests are mocked transport tests.

## Completion gate

Phase16 architecture is engineering-ready when Python CI passes; it is
**deployment-complete only after** scheduler registration on the actual M10
runtime, *successful encrypted cloud roundtrip*, a *verified new-file
restoration* and monitored successful re-run. Document real evidence,
including backup name, size, SHA256 and restore result privately; do not
publish licensed data or credentials.
