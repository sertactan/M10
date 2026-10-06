# Phase 9 — Desktop UI

## Status

**COMPLETE — canonical V1.2/V1.4 desktop UI and acceptance matrix implemented.**

Dependency chain:

```text
main
  └─ Phase 5 — S15.3 V1.4
       └─ Phase 6 — Historical Backtest
            └─ Phase 7 — Market Scanner
                 └─ Phase 8 — Forecast Engine
                      └─ Phase 9 — Desktop UI
```

Phase 9 must not manufacture model output to make the interface look complete.

## Implemented in the first UI slice

- PySide6 desktop shell
- dark navy / restrained gold terminal theme
- global header
  - application title
  - United States market selector
  - ticker input
  - analysis-date picker
  - TODAY button
  - 12-month horizon selector
  - RUN ANALYSIS button
- V1.2 tab
- V1.4 tab
- COMPARE tab
- reusable model score/detail cards
- metric/component table surface
- non-blocking QRunnable/QThreadPool analysis worker
- fresh database connection per analysis worker
- real canonical V1.2 input/model binding
- canonical V1.4 execution with dual-magnitude components surfaced in the metric table
- no synthetic consensus/winner/conviction
- canonical Stock Header bound to `canonical_price_selection` + Parquet
- real day-over-day change from the last two canonical adjusted-close bars
- Phase 6 Historical Backtest card bound to persisted `forward_outcomes`
- Phase 8 Forecast card bound to persisted/hash-validated `forecast_runs`
- explicit `NOT AVAILABLE` / invalid stored forecast states instead of generated placeholders
- canonical historical adjusted-close chart on V1.2 and V1.4 pages
- analysis-date marker on the historical chart
- separate Market Scanner dialog bound to the Phase 7 scanner engine
- scanner runs off the UI thread
- sortable scanner result table, exchange filter and CSV export action
- production scanner uses canonical V1.2/V1.4 scoring
- indeterminate loading indicators for analysis and scanner jobs
- controls disabled during background work and restored on success/error
- Enter-to-run ticker workflow
- minimum responsive window/dialog sizes and adaptive scanner columns
- default application entry now launches the desktop UI

## No-mock rule

Initial UI values are neutral placeholders such as `—` and `NOT LOADED`.
The UI does not ship random/demo stock scores as production results.


## Final UI acceptance gate

The exact Phase 9 UI acceptance matrix is encoded in `app/ui/acceptance.py`.
CI success plus this matrix is required for closure. Canonical V1.4 is executable; M10_D, M10_C, DMG and EA10 diagnostics are exposed through the model component surface.
