# Production Evidence Orchestrator

Runs the completed Meridyen walk-forward chain in one command:

```text
preflight
  -> WF5 PIT whole-market replay
  -> WF6 expanding OOS walk-forward
  -> WF7 OOS validation/calibration
  -> WF8 production hardening
  -> WF8-C reproducibility manifest
  -> optional WF8-D activation
```

The orchestrator is fail-closed.

## Preflight requirements

For the requested historical window:

- exact PIT universe snapshots must exist
- universe cannot be empty
- canonical `BACKTEST` or `BACKTEST_ADJUSTED` price coverage must exist

Stooq `SCANNER_BOOTSTRAP / RAW_ONLY` data does not satisfy this gate.

## Run without activation

```powershell
python scripts/run_production_evidence_chain.py ^
  --start 2013-01-01 ^
  --end 2024-12-31 ^
  --code-identity <GIT_COMMIT>
```

## Run and activate hardened calibration

```powershell
python scripts/run_production_evidence_chain.py ^
  --start 2013-01-01 ^
  --end 2024-12-31 ^
  --code-identity <GIT_COMMIT> ^
  --activate
```

Activation occurs only after WF8 returns `PRODUCTION_EVIDENCE_READY` and a
verified reproducibility manifest has been created.
