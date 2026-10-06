# Data Fabric V2 — Production Release Checklist

Phase 10 release gate. A production release is allowed only when every required
item below is green on the exact release commit.

## Automated gates

- [ ] Python CI / full pytest suite passes.
- [ ] Production audit failure-simulation tests pass.
- [ ] Network outage falls back to valid Last-Known-Good data when available.
- [ ] Corrupt cache never becomes canonical evidence.
- [ ] HTTP 429 / rate-limit failures reduce provider capacity score and open the circuit at threshold.
- [ ] Provider outage preserves canonical priority and uses an already-ready fallback without source blending.
- [ ] SQLite PRAGMA quick_check is ok.
- [ ] Local provider-health benchmark remains within the CI guardrail.
- [ ] Windows application builds successfully.
- [ ] Packaged SQLite schema is present.
- [ ] Packaged US SEC seed is present and passes minimum row count.
- [ ] Packaged JP/TR/HK reference seed is present and passes row-count gates.
- [ ] Clean-install offline first-run smoke test passes.
- [ ] Corrupt-database recovery smoke test passes and preserves a .bak copy.
- [ ] Upgrade migration smoke test passes and preserves legacy rows.
- [ ] Windows installer builds and SHA256 is generated.
- [ ] Release artifact uploads successfully.

## Canonical-policy gates

- [ ] SEC remains authoritative for regulatory fundamentals.
- [ ] Historical price selection remains single-provider; no cross-provider stitching.
- [ ] Yahoo-compatible data remains fallback/confirmation-only, not authoritative backtest evidence.
- [ ] Historical PIT universe requests fail closed when no valid PIT archive is available.
- [ ] Reference-only JP/TR/HK listings are not silently promoted to canonical evidence.
- [ ] No paid API key is required for baseline startup.
- [ ] Mock data remains forbidden in production.
- [ ] Strict PIT remains enabled.

## Operational targets

The release audit treats the roadmap scores as release targets backed by the
gates above; it does not manufacture a numeric score from missing evidence.

- Data integrity target: >= 9.8/10.
- Availability target: >= 9.8/10.
- Speed target: >= 9.7/10.
- Fault tolerance target: >= 9.8/10.
- Offline capability target: >= 9.7/10.

Any failed required gate blocks the production release.
