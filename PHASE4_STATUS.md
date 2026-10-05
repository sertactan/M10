# Phase 4 — S15.3 V1.2 Canonical Scoring Engine

## Authoritative model sources

The implementation is bound to these user-provided canonical sources:

1. `Meridyen_S15.3_Canonical_Final_Spec_v1.0.md`
2. `Meridyen_S1-S14_Canonical_Analysis_Spec_v1.0.md`
3. Router / Gate rules contained in the canonical S15.3 specification
4. `Meridyen_10X_Historical_Dataset_Matched_Control_Spec_v1.0.md`
5. Canonical worked examples supplied with the S15.3 design

No separate standalone "Golden Test Cases" file was found in the available project files.
Therefore no ticker-specific expected score was invented. The canonical worked examples and
formula invariants are used as regression tests.

## Implemented

- canonical helper math: Clip / WA / PosScore / NegScore / AccelScore / PiecewiseScore
- Core48 nine families
- Control12
- DNA60
- S1 router C/I/Y
- Historical H formula
- N61
- S1 / S2 / S3
- S14 weighted geometric earnings-quality triangulation
- Company Quality
- S15.3 V1.2 routes:
  - F10
  - I10
  - D10
  - B10
  - R10
  - Q10
- route blend RB
- route essential coverage
- bottleneck penalty BP
- route gates
- U / ETRQ / FCVX / RER
- Catalyst C
- Market Confirmation M
- Regime Fit G
- Viability V
- Precursor Acceleration A
- Precursor Velocity X
- DF5 / DF10 final destination-ratio scoring
- MCH5 / MCH10
- CMAG
- H10 / HMG10 historical similarity helpers
- PIR
- M5 / M10
- MAGGAP / NMP
- PV / MI / REV / RA / FLOW / EXEC
- T10 / T15
- HP
- Core15.3
- final S15.3
- Discovery / Strong Watch / Precision Confirmed gates
- near-miss and horizon flags
- exact canonical confidence formula when all four confidence legs exist
- minimum-data fail-closed behavior

## Data-provider rule

Phase 4 introduces no market-data or fundamental-data provider.

The model accepts only PIT model features materialized from:

- PHASE1_UNIVERSE
- PHASE2_PRICE
- PHASE3_FUNDAMENTAL
- HISTORICAL_CONTROLS
- DERIVED_CANONICAL

Direct provider names such as FINNHUB, MASSIVE, FMP, Yahoo, etc. are rejected as
`source_phase` values in the Phase 4 feature repository. Provider data must first pass through
the canonical data layer built in Phases 1–3.

## Missing-data rule

Missing factors are stored as N/A / None. They are never silently converted to zero.

S15.3 is `INCONCLUSIVE` unless:

- S15.2 is available
- M10 has at least 5/7 legs
- T10 has at least 5/7 legs
- selected route essential coverage is at least 70%

H10 and XR are the only positive S15.2 legs explicitly permitted by the canonical spec to be
missing with positive-weight renormalization; Precision Confirmed is then impossible.

## CLI

```powershell
python main.py --run-v12 AAPL --model-as-of 2025-05-05
```

The run is persisted with:

- data snapshot hash
- model config hash
- all available intermediate components
- route scores
- final flags

## CI validation
GitHub Python CI runs compileall and the complete pytest suite before Phase 4 is merged.
