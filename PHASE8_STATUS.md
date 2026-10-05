# Phase 8 — Forecast Engine

## Status

**STARTED on a dependency branch; forecast orchestration implemented, production calibration remains fail-closed.**

Dependency chain:

```text
main
  └─ Phase 5 — S15.3 V1.4
       └─ Phase 6 — Historical Backtest
            └─ Phase 7 — Market Scanner
                 └─ Phase 8 — Forecast Engine
```

Phase 8 must not merge ahead of the canonical Phase 5/6/7 chain.

## Master-prompt scope

Phase 8 is limited to:

- current-date predictions
- probability calibration
- 12-month forward mode
- forward probability
- confidence
- expected return range / bull-base-bear scenarios
- risk
- explicit disclosure that the result is a forecast, not a realized outcome

The numerical examples in the master prompt are examples only and are not treated as canonical
probability mappings or scenario formulas.

## Implemented

- `core/forecast/contracts.py`
- `core/forecast/calibration.py`
- `core/forecast/engine.py`
- current-date-only mode guard
- 12-month canonical horizon guard
- canonical Phase 4/5 dual-model scorer dependency
- external calibration-provider contract
- fail-closed default when historical calibration is unavailable
- calibration cutoff firewall: calibration evidence cannot be newer than forecast `as_of`
- probability range validation
- monotone magnitude probabilities: positive >= 2X >= 5X >= 10X
- ordered scenarios: bear <= base <= bull
- explicit forward-estimate disclosure

## Production activation gate

Phase 8 remains production-blocked until:

1. Phase 5 V1.4 is canonical and executable.
2. Phase 6 walk-forward / market-prevalence backtest is complete.
3. An authoritative calibration method is bound to Phase 6 evidence.
4. Calibration outputs are reproducible and carry a calibration id, cutoff, source and sample size.
5. Production tests confirm no look-ahead and no hard-coded/example probabilities.

No scenario return or probability mapping is invented by Phase 8.
