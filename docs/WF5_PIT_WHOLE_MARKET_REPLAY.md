# WF5 — PIT Whole-Market Replay

Status: COMPLETE — score/outcome phases, censoring and historical-control feed implemented.

## Physical sequence

For every requested PIT snapshot date:

1. Require exact historical universe membership.
2. Run WF3 destination/peer materialization.
3. Preliminary V1.2/V1.4.1 scoring for outcome-independent route/components.
4. Materialize WF4 H10/HMG5/HMG10/XR using only labels whose
   `label_available_at <= target_as_of`.
5. Re-run final V1.2 + V1.4.1 scoring.
6. Persist scores with `outcome_status=NOT_JOINED`.
7. Only after score persistence, join the canonical 252-session forward outcome.
8. READY labels are written to the WF4 historical cohort store with
   `label_available_at` equal to the 252nd forward session date.
9. PARTIAL paths are CENSORED, never treated as failures.

No future outcome is available to the same observation's score phase.

## Canonical price gate

Outcome join tries:

```text
BACKTEST_ADJUSTED
BACKTEST
```

A Stooq RAW_ONLY / SCANNER_BOOTSTRAP selection is not eligible.

Missing canonical price history becomes:

```text
CENSORED_NO_CANONICAL_PRICE
```

not FAILURE.

## Resume

Per-date checkpoints:

```text
SCORE
OUTCOME_JOIN
```

Completed phases are skipped on resume. Runs with blocked/non-PIT dates or
remaining errors finish as `COMPLETE_WITH_BLOCKERS`.

## Default run

```powershell
python scripts/run_wf5_replay.py --start 2013-01-01 --end 2024-12-31
```

Resume an existing run:

```powershell
python scripts/run_wf5_replay.py --start 2013-01-01 --end 2024-12-31 --run-id <RUN_ID>
```
