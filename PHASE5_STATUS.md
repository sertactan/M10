# Phase 5 — S15.3 V1.4 Dual-Magnitude Architecture

## Status

**STARTED — canonical architecture added; scoring remains fail-closed pending the authoritative V1.4 specification set.**

Phase 5 does not introduce a new market-data or fundamental-data provider. It consumes the
same normalized, Point-in-Time canonical feature layer built by Phases 1-3 and used by Phase 4.

## Added

- separate `S153V14Model` class
- separate V1.4 input/result contracts
- V1.4 PIT input loader backed only by `ModelFeatureRepository`
- result fields reserved for:
  - route-specific destination
  - dual magnitude
  - asymmetric-candidate diagnostics
  - acceleration
  - large-winner probability
  - risk-adjusted conviction
  - confidence
  - probability buckets
- hard fail-closed canonical-spec binding gate
- regression tests proving that plausible-looking feature names cannot activate invented V1.4 logic

## Authoritative sources still required

The engine will remain disabled until all of the following are available as explicit canonical
artifacts:

1. S15.3 V1.4 Canonical Specification
2. V1.4 Factor / DNA Definitions
3. V1.4 Router and Gate Specification
4. Dual-Magnitude / Destination Specification
5. Golden Test Cases

The currently available project material describes V1.4 architecture and UI examples, but does
not provide a complete authoritative set of V1.4 formulas, factor weights, thresholds, route
gates, probability mappings, destination rules, magnitude buckets, confidence rules, and
missing-data treatment.

## No-invention rule

Until those artifacts are bound, Phase 5 must not invent or modify:

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

The correct runtime behavior is therefore to fail closed instead of returning a fabricated
score, probability, route, or destination.
