# WF5 — PIT Whole-Market Replay

Status: STARTED.

## Architecture

WF5 is split into physically separate phases:

1. SCORE
2. OUTCOME_JOIN

The SCORE phase may read only evidence available at the snapshot date. It:
- requires an exact PIT universe snapshot,
- runs WF3 destination materialization,
- scores V1.2 + V1.4.1,
- persists score/status/route,
- leaves `outcome_status=NOT_JOINED`.

The future 252-session outcome is joined only in a later phase after scoring is
persisted. This preserves the existing score-before-outcome firewall.

## Default research schedule

2013-01 through 2024-12 month-end = 144 requested snapshots.

A snapshot with no exact PIT universe is blocked rather than substituted with
today's universe.

## Resume/checkpoint

`wf5_replay_checkpoints` stores per-date phase status and counts. Re-running a
date is deterministic/upsert-safe at the observation key:

```text
run_id | security_id | as_of_date
```

Outcome join and censoring are the next WF5 milestone.
