# Phase 6 — Historical Backtest Engine

## Status

**STARTED on a dependent branch.**

Branch dependency:

```text
main
  └─ Phase 5 — S15.3 V1.4
       └─ Phase 6 — Historical Backtest Engine
```

Phase 6 must not be merged ahead of Phase 5. Full dual-model evaluation is intentionally blocked
while the authoritative V1.4 engine remains fail-closed.

## Data-source rule

Phase 6 adds no independent market-data or fundamental-data provider.

Historical prices are loaded only from a prior `canonical_price_selection` produced by the
Phase 2 canonical price layer. PIT model inputs come from the existing canonical feature layer.

## Model-source rule

Full evaluation calls:

- Phase 4 `S153V12Model`
- Phase 5 `S153V14Model`

Model scoring occurs before forward outcomes are computed/joined.

## Canonical outcome logic already bound

The available `Meridyen_10X_Historical_Dataset_Matched_Control_Spec_v1.0.md` defines and Phase 6 implements:

- observation key: `security_id × as_of_date`
- `anchor_session = last completed trading session <= as_of_date`
- anchor price = adjusted close
- forward path = next 252 sessions
- `FM252 = max(next 252 adjusted closes) / anchor adjusted close`
- TRUE_10X / NEAR_MISS_10X / MAJOR_WINNER / STRONG_WINNER / MODERATE_WINNER / FAILURE classes
- time-to-2x/3x/5x/7x/10x from adjusted closes
- reliable terminal consideration support
- unknown terminal value => `CENSORED`
- incomplete non-terminal 252-session path => `PARTIAL`
- cross-provider price stitching rejection
- prediction error classes: TP / Near-Miss FP / Magnitude FP / Strong-Winner FP / Hard FP
- physical/logical feature-vs-outcome firewall
- outcome hash persistence

## Authoritative source coverage

Required by Phase 6:

1. Historical Backtest Specification — **BOUND/PARTIAL via matched-control canonical spec**
2. Point-in-Time Controls Specification — **BOUND via matched-control spec + master PIT rules**
3. Corporate Action Adjustment Specification — **PARTIAL; exact standalone artifact not found**
4. Trading Calendar Specification — **PARTIAL; anchor/252-session semantics found, complete artifact not found**
5. Benchmark Specification — **MISSING**
6. Golden Backtest Test Cases — **MISSING**

Missing/partial specifications are not guessed.

## Tables

Phase 6 adds:

- `forward_outcomes`
- `backtest_predictions`
- `backtest_run_manifest`

Existing `backtest_results` remains untouched for compatibility.

## Activation gate

Production/full Phase 6 remains fail-closed until:

- Phase 5 V1.4 is canonical and executable
- all six authoritative Phase 6 artifacts are bound
- Golden Backtest Test Cases pass
