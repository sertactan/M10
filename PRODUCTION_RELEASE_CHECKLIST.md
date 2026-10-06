# Data Fabric V2 — Production Release Checklist

Phase 10 release gate. A production release is allowed only when every required
item below is green on the exact release commit.

## Automated gates

- [x] Python CI / full pytest suite passes.
- [x] Production audit failure-simulation tests pass.
- [x] Network outage falls back to valid Last-Known-Good data when available.
- [x] Corrupt cache never becomes canonical evidence.
- [x] HTTP 429 / rate-limit failures reduce provider capacity score and open the circuit at threshold.
- [x] Provider outage preserves canonical priority and uses an already-ready fallback without source blending.
- [x] SQLite PRAGMA quick_check is ok.
- [x] Local provider-health benchmark remains within the CI guardrail.
- [x] Windows application builds successfully.
- [x] Packaged SQLite schema is present.
- [x] Packaged US SEC seed is present and passes minimum row count.
- [x] Packaged JP/TR/HK reference seed is present and passes row-count gates.
- [x] Clean-install offline first-run smoke test passes.
- [x] Corrupt-database recovery smoke test passes and preserves a .bak copy.
- [x] Upgrade migration smoke test passes and preserves legacy rows.
- [x] Windows installer builds and SHA256 is generated.
- [x] Release artifact uploads successfully.

## Canonical-policy gates

- [x] SEC remains authoritative for regulatory fundamentals.
- [x] Historical price selection remains single-provider; no cross-provider stitching.
- [x] Yahoo-compatible data remains fallback/confirmation-only, not authoritative backtest evidence.
- [x] Historical PIT universe requests fail closed when no valid PIT archive is available.
- [x] Reference-only JP/TR/HK listings are not silently promoted to canonical evidence.
- [x] No paid API key is required for baseline startup.
- [x] Mock data remains forbidden in production.
- [x] Strict PIT remains enabled.

## Operational targets

The release audit treats the roadmap scores as release targets backed by the
gates above; it does not manufacture a numeric score from missing evidence.

- Data integrity target: >= 9.8/10.
- Availability target: >= 9.8/10.
- Speed target: >= 9.7/10.
- Fault tolerance target: >= 9.8/10.
- Offline capability target: >= 9.7/10.

Any failed required gate blocks the production release.


## Verification evidence

Audited runtime commit: `ec76b3ec0d9e2b672b0c2ef230199d3730eb2a5e`

- Python CI run: 37458878947 — SUCCESS.
- Windows Production Build run: 37458878832 — SUCCESS.
- Windows build passed packaged schema/seed checks, offline clean-install,
  corrupt-database recovery, upgrade migration, installer build, SHA256, and
  artifact upload.
- Canonical-policy gates were re-audited against the same runtime commit:
  SEC regulatory precedence, single-source price selection, Yahoo fallback-only,
  historical PIT fail-closed behavior, JP/TR/HK REFERENCE_ONLY scope, no paid
  baseline dependency, strict PIT enabled, mock data disabled.

The roadmap numeric values remain engineering targets rather than fabricated
measured scores. Phase 10 is closed because every implemented release gate
required by the roadmap passed on the audited runtime commit.
