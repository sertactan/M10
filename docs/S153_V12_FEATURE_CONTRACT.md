# S15.3 V1.2 Canonical Feature Contract

Phase 4 does not call external providers. It consumes PIT feature rows from
`canonical_model_features`.

## Storage naming

### Discovery DNA

```text
D01 ... D48
```

All are canonical 0–100 scores.

### Failure-control DNA

```text
F49_MCR
F50_TAMMC
F51_GP
F52_RPS
F53_FPS
F54_DIL
F55_IROIC
F56_ORG
F57_UE
F58_MOAT
F59_CAPINT
F60_CONC
```

All are canonical 0–100 quality scores.

### Raw monetary / market-cap inputs

These are NOT 0–100 scores:

```text
RAW_CURRENT_PRICE
RAW_CURRENT_MARKET_CAP
MEDIAN_DOLLAR_VOLUME_20
SUPPORTED_MC_12_FI
SUPPORTED_MC_12_D
SUPPORTED_MC_12_B
SUPPORTED_MC_12_R
PLAUSIBLE_CEILING_MC
```

Route-specific SupportedMC values must be generated using the canonical destination rules.
If the evidence needed by a destination rule is absent, the field stays N/A.

### Historical controls

```text
WINNER_SIM
CONTROL_SIM
H10
HMG5
HMG10
XR
```

These are 0–100 scores produced by the historical-control layer. Forward outcomes may be used
only to construct historical labels/cohorts, never as a current observation feature.

### Confidence

```text
DATA_COVERAGE
SOURCE_QUALITY
PIT_INTEGRITY
MODEL_FIT
```

Each is 0–100. Phase 4 applies exactly:

```text
Confidence =
0.40 DataCoverage +
0.25 SourceQuality +
0.20 PITIntegrity +
0.15 ModelFit
```

No confidence leg is guessed when missing.

## Provenance fields

Every materialized feature must retain:

```text
security_id
feature_key
value
feature_as_of
available_at
source_phase
source_ref
quality_status
computation_version
evidence_json
```

`available_at <= feature_as_of` is enforced.

## Allowed source phases

```text
PHASE1_UNIVERSE
PHASE2_PRICE
PHASE3_FUNDAMENTAL
HISTORICAL_CONTROLS
DERIVED_CANONICAL
```

A direct external provider cannot bypass the Phase 1–3 canonical layer.
