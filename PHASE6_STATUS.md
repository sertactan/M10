# Phase 6 — Historical Backtest Engine

## Status

**COMPLETE on the dependent branch — canonical runtime active.**

Branch dependency:

```text
main
  └─ Phase 5 — S15.3 V1.4
       └─ Phase 6 — Historical Backtest Engine
```

Phase 5 V1.4 is now canonical and executable. Full dual-model evaluation is active.

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

## Canonical source coverage

The matched-control specification plus master PIT rules are the authoritative runtime basis for
anchor selection, 252-session outcomes, censoring, survivorship handling and leakage controls.
Unknown corporate-action/calendar details remain fail-closed; no terminal session index is invented.

The six-artifact bundle loader remains available as optional audit packaging. It is not a runtime
activation requirement and does not introduce benchmark mathematics absent from the project spec.

## Tables

Phase 6 adds:

- `forward_outcomes`
- `backtest_predictions`
- `backtest_run_manifest`

Existing `backtest_results` remains untouched for compatibility.

## Canonical bundle ingestion gate

The repository now includes `core/backtest/spec_bundle.py` and a dedicated drop location at `specs/phase6_backtest/`.

A complete Phase 6 source package must contain exactly the six required authoritative artifacts and a `manifest.json` that pins every artifact by SHA-256. Missing, duplicate, empty, path-escaping, tampered, invalid-hash, placeholder, or incomplete bundles are rejected. Verification does not authorize guessed benchmark rules or Golden expected values; executable behavior must still be copied exactly from the verified artifacts.

## Activation gate

**PASS** — canonical V1.4 is executable and Phase 6 runtime tests cover PIT separation,
252-session outcomes, censoring, terminal consideration and provider isolation.

