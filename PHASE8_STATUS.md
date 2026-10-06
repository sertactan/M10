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
- validated calibration profile persistence (`forecast_calibration_profiles`)
- Market Prevalence-only calibration evidence gate
- walk-forward / leakage / survivorship audit PASS requirements
- hashed calibration evidence and tamper detection
- reproducible forecast-run persistence with deterministic `analysis_id`
- forecast payload SHA-256 (`forecast_hash`)
- required `data_snapshot_hash` + `model_config_hash`
- route/destination/model-version provenance
- exact Phase 8 acceptance matrix
- pinned calibration-provider adapter (no implicit score-bucket inference)
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

## Historical calibration binding

Phase 8 now has a persistence/binding pipeline for upstream Phase 6 calibration outputs. The pipeline does **not** fit or derive probabilities. It accepts only externally computed calibration values that are tied to an existing backtest run and pass the required evidence gates.

Production calibration is restricted to `MARKET_PREVALENCE` evidence. Matched-challenge/case-control output is not accepted as market probability evidence. Required evidence includes walk-forward PASS, leakage-audit PASS, survivorship-audit PASS, and explicit proof that future outcome columns were absent from the feature matrix. Evidence is hashed before persistence and rechecked on load.

The score/route-to-calibration-bucket selection rule remains intentionally external until an authoritative calibration mapping is supplied.


## Reproducibility and acceptance

Every persisted forecast run is tied to:

- security id / ticker / analysis date
- 12M horizon
- V1.2 and V1.4 model versions
- model scores, routes and destinations
- calibration id, cutoff, sample size and evidence hash
- data snapshot SHA-256
- model-config SHA-256
- complete forecast payload SHA-256
- deterministic analysis id

The Phase 8 completion gate is encoded in `core/forecast/acceptance.py`.
CI success alone does not make Phase 8 production-complete. In particular,
`V1.4 canonical scoring` and genuine Market Prevalence calibration must pass
before the phase can be closed.
