# Phase 10 — Model Analytics

## Status

**COMPLETE on the dependent branch; acceptance tests pass.**

Scope from the master prompt:

- score buckets
- route performance
- false positives
- V1.2 vs V1.4 comparison

## Implemented

- persisted backtest evidence only
- explicit caller-supplied score buckets; no invented bucket thresholds
- bucket count / average score / average FM252 / 10X count / precision-confirmed count
- false-positive breakdown using the canonical Phase 6 error classifier
- route performance from persisted historical analysis/backtest rows
- paired V1.2 vs V1.4 comparison on the same observations
- READY-only outcome filtering

Phase 10 must remain dependency-aware while canonical V1.4 / Phase 6 production evidence is incomplete.


## Final acceptance gate

The exact Phase 10 completion matrix is encoded in `core/analytics/acceptance.py`.
