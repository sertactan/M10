# Phase 9 — Desktop UI

## Status

**STARTED on a dependent branch.**

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
- V1.4 fail-closed UI state when the canonical Phase 5 specification is unavailable
- no synthetic consensus/winner/conviction
- default application entry now launches the desktop UI

## No-mock rule

Initial UI values are neutral placeholders such as `—` and `NOT LOADED`.
The UI does not ship random/demo stock scores as production results.

## Remaining Phase 9 work

- dedicated stock header with canonical price/change
- V1.4 dual-magnitude detail surface once V1.4 is executable
- forecast cards bound to Phase 8
- historical backtest result cards bound to Phase 6
- historical price chart
- scanner table bound to Phase 7
- loading/progress/error refinements
- responsive layout polish
- final UI acceptance tests
