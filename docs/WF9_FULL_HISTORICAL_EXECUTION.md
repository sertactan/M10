# WF9 — Full Historical Execution & Evidence Generation

Status: IMPLEMENTED / EXECUTION PENDING REAL DATA.

WF9 is the first phase whose primary goal is **running** the completed WF1-WF8
stack rather than defining another scoring formula.

Default evidence window:

```text
PIT observations: 2013-01 through 2024-12 (144 monthly snapshots)
OOS folds:        2018 through 2024
```

Execution chain:

```text
preflight
 -> WF5 whole-market replay
 -> WF6 expanding walk-forward
 -> WF7 validation/calibration
 -> WF8 hardening
 -> WF8-C reproducibility manifest
 -> WF8-D production activation
```

## Preflight

WF9 fails closed before computation when:

- a requested monthly PIT snapshot is missing;
- any snapshot is not exact PIT;
- there is no canonical adjusted backtest price evidence at all.

Partial adjusted-price coverage is reported explicitly as a censoring-risk
warning. It is not silently converted into negative outcomes.

## Data bootstrap

The v1.0.6 branch adds a resumable real-data bootstrap. It never promotes Yahoo fallback data or Stooq RAW_ONLY data to authoritative backtest evidence.

```powershell
python scripts/bootstrap_wf9_canonical_data.py ^
  --start 2013-01-01 ^
  --end 2024-12-31 ^
  --sync-universe ^
  --provider AUTO
```

The PIT universe step requires a configured PIT-capable source (the bundled free workflow uses `ALPHAVANTAGE_API_KEY`). Canonical adjusted prices require an authoritative adjusted source accepted by the Phase 2 policy, such as configured Massive, MarketParquet, or SimFin data. The command is resumable and writes `data/runtime/wf9_bootstrap_report.json`.

## Commands

Preflight only:

```powershell
python scripts/run_wf9_full_execution.py ^
  --preflight-only ^
  --code-identity <CURRENT_BUILD_COMMIT>
```

Full execution:

```powershell
python scripts/run_wf9_full_execution.py ^
  --code-identity <CURRENT_BUILD_COMMIT>
```

A successful run ends at `COMPLETE_AND_ACTIVATED` and returns all WF5/WF6/WF7/
WF8/manifest/activation identifiers.

The free-data design remains fail-closed: if the local database lacks a
canonical adjusted historical price source, WF9 reports
`NO_CANONICAL_ADJUSTED_BACKTEST_PRICE` rather than treating Stooq RAW_ONLY or
another fallback as authoritative backtest evidence.

## Release truth condition

Documentation status must not be changed to production-complete merely because the orchestration code exists. The only completion state is a real execution report whose status is `COMPLETE_AND_ACTIVATED`. As of the v1.0.6 implementation branch, that real-data execution has not been produced inside GitHub because the required historical runtime database/provider credentials are external to the repository.
