# Phase 13 — M10 ↔ Meridyen Real-Data / PIT Bridge

**Status: ENGINEERING_READY; REAL_DATA_ACTIVATION_BLOCKED**  
Date: 2026-10-08  
Branch: `feat/phase13-pit-learning-bridge-20261008`

## Implemented (code)

1. Strengthened `WF9FullHistoricalExecution.preflight` to fail closed on missing monthly PIT snapshots, missing canonical adjusted-price dates, partial eligible-member adjusted-price coverage, missing fundamental facts, missing PIT features or missing V1.4.1 upstream route/destination features. Existing model weights and formulas unchanged.
2. `scripts/phase13_export_signals.py`: exports only observed ready canonical S15.3 V1.4.1 scores from a *completed* WF5 historical run. Preserves security ID and observation ID and writes SHA-256 manifest; excludes inconclusive outputs.
3. Regression tests for incomplete WF5 exports, score/status filtering and partial PIT coverage.
4. Learning Engine V2 local-first SQLite journal, deduplicated source hashes, censored outcomes, noncanonical evidence audits and a transactionally consistent SQLite snapshot backup.
5. Explicit, **opt-in** encrypted rclone upload helper; no secret/config added to GitHub. User's Drive folder structure was created separately, but rclone/M10 runtime authorization is not yet configured.

## Cannot honestly mark as complete

M10's **local canonical historical SQLite / Parquet data, API credentials, full 2013–2024 PIT snapshots and production WF9 evidence are not available in this remote workspace**. Repo code alone is not proof of actual dataset coverage. Current code requires actual `COMPLETE_AND_ACTIVATED` result from `scripts/run_wf9_full_execution.py` before declaring full Phase13 historical execution complete.

### Production steps (run on the machine with M10 and licensed/permitted data)

```powershell
python scripts/wf9_environment_probe.py
python scripts/bootstrap_wf9_canonical_data.py --start 2013-01-01 --end 2024-12-31 --sync-universe --provider AUTO
python scripts/run_wf9_full_execution.py --code-identity <CURRENT_BUILD_COMMIT> --preflight-only
# Only if preflight succeeds:
python scripts/run_wf9_full_execution.py --code-identity <CURRENT_BUILD_COMMIT> --output release_evidence/WF9_PRODUCTION_EVIDENCE.json
# Replace the sample run ID with a genuinely COMPLETE WF5 run ID from output:
python scripts/phase13_export_signals.py --db data/runtime/operational.db --run-id <COMPLETE_WF5_RUN_ID> --out-dir data/runtime/phase13_export
```

Caveat: installed Windows M10 uses a writable runtime directory that may differ from relative repository `data/runtime`; provide actual DB path to exporter.

## Next real-data integration

- Export matching authoritative adjusted daily price history as a separate file, with split/corporate-action checks and delisted members; never use the present ticker list as a PIT universe.
- Use Meridyen plugin v0.12 daily-backtest runners on **verified** matching date/source input CSVs. Join with source IDs and flags; do not call the resulting proxy "PIT certified" without independent audit.
- Ingest mature results into Learning V2; preserve original source evidence. Run actual OOS and matched-control tests before comparing model quality.
- Connect an encrypted rclone crypt remote to the newly created private Google Drive folder for cloud backups; never treat GitHub as a raw-data storage endpoint.

## Testing

GitHub CI runs `python -m pytest -q` on pull requests. New tests included in `tests/test_phase13_bridge.py`, `tests/test_wf9_execution.py` and `tests/test_learning_v2.py`. No real-market performance metric has been asserted.

## Follow-up — Phase 13 one-command real-data readiness (2026-10-08)

Now includes `scripts/phase13_readiness_report.py` and the guarded
`scripts/phase13_windows_pipeline.ps1` entry point. The reporter opens
M10's actual database **read-only** and generates:

- `data/runtime/phase13_readiness/PHASE13_READINESS.json`
- `data/runtime/phase13_readiness/PHASE13_READINESS.md`

Checks the exact native WF9 PIT coverage on the requested 2013–2024
window, shows missing monthly dates and coverage counts, and preserves
`PREFLIGHT_BLOCKED` / `BLOCKED_DB_NOT_FOUND` states honestly.

**On the actual M10 Windows machine**, from source repo root:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/phase13_windows_pipeline.ps1
# Or, if the application has a custom writable runtime:
$env:S153_RUNTIME_ROOT = "D:\MeridyenRuntime"
powershell -ExecutionPolicy Bypass -File scripts/phase13_windows_pipeline.ps1
# Once the diagnostic says PREFLIGHT_READY_NOT_ACTIVATED:
powershell -ExecutionPolicy Bypass -File scripts/phase13_windows_pipeline.ps1 -Execute
```

`-Execute` performs the native WF9 run and **activates** only if the
preflight passes; it does not bootstrap/download data or bypass gates.
Check permissions/data licenses before any provider bootstrap.

The updated GitHub-hosted WF9 Environment Probe workflow also produces
`PHASE13_READINESS.json` and `.md` CI artifacts. Its hosted runner is
a different machine from the user's Windows M10 runtime. A missing DB there
is not evidence that the user has no local market data.

No real-market WF9 completion, PIT certification, or continuous Learning V2
has been claimed from the hosted test alone.
