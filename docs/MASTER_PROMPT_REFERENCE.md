# Master Prompt Reference

This project treats the following user-supplied file as the original/master product prompt:

- file: `S15.3_Desktop_Stock_Analysis_Backtest_Master_Prompt(1).md`
- SHA-256: `9c90dea8b44a22a6d8f006a1040eb235a4ba78145fa3fd5a8c9c94b607c94e74`
- size: 21,913 bytes
- role: project-level reference for architecture, data rules, phase sequencing, UI intent, PIT behavior, reproducibility, no-mock-data policy, and acceptance expectations

## Non-negotiable project rules carried from the master prompt

1. Historical analysis is Point-in-Time and must not use future information.
2. S15.3 V1.2 and S15.3 V1.4 are separate model engines.
3. V1.4 must not be created by casually extending or mutating V1.2 logic.
4. Production results must come from real data and real model calculations; mock/demo/random scores are forbidden.
5. Missing data must be explicit rather than silently substituted.
6. Model calculations stay separated from UI.
7. Canonical/default model configuration stays version-controlled.
8. Each analysis must be reproducible with data/model hashes.
9. Phase 5 is the V1.4 Dual-Magnitude phase and must precede historical backtesting, scanning, forecasting, and UI integration.

## Phase 5 binding rule

Phase 5 uses normalized Point-in-Time data from Phases 1-3. No new external provider may be introduced unless a required V1.4 input cannot be produced by the canonical data layer.

Authoritative model specifications:

1. S15.3 V1.4 Canonical Specification
2. V1.4 Factor / DNA Definitions
3. V1.4 Router and Gate Specification
4. Dual-Magnitude / Destination Specification
5. Golden Test Cases

Until those specifications are present, the implementation must not invent or modify:

- formulas
- factor weights
- thresholds
- routes
- gates
- penalties
- probability mappings
- destination rules
- magnitude buckets
- confidence rules
- missing-data treatment

The runtime must fail closed rather than fabricate V1.4 outputs.
