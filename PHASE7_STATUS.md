# Phase 7 — Market Scanner

**COMPLETE** — canonical V1.2/V1.4 production scanner, PIT/current-historical universes and all scanner mechanics are implemented.

## Dependency chain

```text
main
  └─ Phase 5 — S15.3 V1.4
       └─ Phase 6 — Historical Backtest Engine
            └─ Phase 7 — Market Scanner
```

Phase 5 and Phase 6 are now canonical and merged. Phase 7 is ready for direct merge to main.

## Production architecture

Phase 7 introduces no new market-data or fundamental-data provider.

Universe source:
- current US common stocks from `SecurityRepository.current_us_common_stocks()`
- historical US universe from exact PIT `universe_snapshot_membership`

Model source:
- Phase 4 `S153V12Model`
- Phase 5 `S153V14Model`

PIT feature source:
- existing `ModelFeatureRepository.load_as_of()`
- future feature versions are excluded by `feature_as_of <= as_of` and `available_at <= as_of`

## Scanner capabilities implemented

- current US scan
- historical US scan
- NASDAQ / NYSE / AMEX coverage
- canonical dual-model production scoring adapter
- historical universe preservation
- delisted-security preservation in historical snapshots
- sortable result rows
- filterable result rows
- CSV export
- configurable batch processing
- 10,000+ row infrastructure test
- progress callbacks
- background worker that keeps scan execution off the UI thread

## Phase 7 acceptance contract

The exact required matrix is encoded in `core/scanner/acceptance.py`:

1. Current US scan
2. Historical US scan
3. NASDAQ coverage
4. NYSE coverage
5. AMEX coverage
6. V1.2 scoring
7. V1.4 scoring
8. PIT filtering
9. Historical universe
10. Delisted handling
11. Sort
12. Filter
13. Export
14. 10,000+ securities batch scan
15. UI remains responsive

## Important production gate

Infrastructure tests are not allowed to substitute fake model outputs for production acceptance.

In particular:

- Phase 4 V1.2 is canonical and executable.
- Phase 5 V1.4 is canonical and executable.
- V1.4 missing inputs return explicit INCONCLUSIVE results rather than fabricated scores.
- The 15-item Phase 7 acceptance contract is fully executable.

Test doubles are used only to prove scanner batching/sort/filter/export/background-worker mechanics.
