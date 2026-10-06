# MERIDYEN DATA FABRIC V2 — FREE-FIRST ROADMAP

Goal: make S15.3/M10 data delivery fast, resilient, local-first, and safe without requiring a paid API subscription.

## Non-negotiable rules

- No paid provider is required for baseline operation.
- SEC EDGAR remains canonical for regulatory fundamentals.
- Cross-provider price stitching is forbidden.
- Fallback-quality data must never silently become authoritative backtest evidence.
- Analysis should prefer local validated data; network access is a refresh path, not a prerequisite.
- Every provider call must be observable, health-scored, and circuit-breaker protected.
- Last-known-good data must remain available during upstream outages.

## Phase 0 — Baseline / acceptance contract

Status: COMPLETE

- Preserve PIT / canonical-data rules.
- Preserve source provenance.
- Define free-first operation.
- Define provider health score:
  - 30% availability
  - 25% freshness
  - 20% data quality
  - 15% latency
  - 10% rate-limit capacity
- Define CLOSED -> OPEN -> HALF_OPEN -> CLOSED circuit-breaker lifecycle.
- Keep existing static provider priority as the cold-start tie breaker.

Acceptance:
- No new paid dependency.
- Existing canonical tests remain valid.

## Phase 1 — Provider Health Router + Circuit Breaker

Status: COMPLETE

Deliverables:
- Persistent provider health state.
- Persistent provider health event log.
- Dynamic health ranking.
- 5-failure default circuit breaker.
- 60-second default cooldown.
- Rate-limit detection.
- Latency and availability scoring.
- Desktop first-run bootstrap protection.
- Price and fundamentals engines can route around unhealthy providers.

Acceptance:
- Unseen providers preserve canonical static priority.
- Failing providers are demoted.
- Circuit opens after threshold.
- Half-open probe occurs after cooldown.
- Success closes and resets failure streak.

## Phase 2 — Local-First + Last-Known-Good

Status: CORE COMPLETE

Deliverables:
- Read local canonical price/fundamental data before any network request.
- Last-known-good snapshots for universe, prices, fundamentals, and model inputs.
- Explicit STALE / FRESH metadata.
- Configurable freshness windows.
- Network outage must not blank the UI when validated cached data exists.

Acceptance:
- CRMD analysis can open from cached state with internet disabled.
- UI reports age/source of cached data.

## Phase 2B — Global Security Master + Offline Seed

Status: COMPLETE

Goal:
- Put a very broad symbol/security reference layer inside M10 without weakening
  canonical S15.3 evidence rules or creating a paid-data dependency.

Bundled/open layer:
- SEC EDGAR current US issuer universe is generated at Windows build time and
  packaged with the installer.
- SEC coverage includes recognized NASDAQ, NYSE, AMEX, OTC, and CBOE rows.
- Fresh installs can populate security_master before the first network request.

Broad local-reference layer:
- Built-in optional sync adapter for the Adanos Free Global Ticker Database.
- 60k+ collision-safe reference listings across dozens of exchanges/countries.
- Imported rows are tagged REFERENCE_ONLY and never become authoritative
  backtest/model evidence merely because they exist in security_master.
- Existing canonical rows are enriched (ISIN/country/listing metadata) without
  being downgraded.

Licensing rule:
- Only data with verified redistribution rights may be physically bundled.
- Mixed/restricted exchange-derived reference datasets are fetched to the
  user's local runtime, not committed into or redistributed with the installer.
- Market-specific official refresh adapters will supersede reference rows when
  licensing and data contracts permit.

Target official local refresh markets:
- US: SEC EDGAR plus current exchange reference validation.
- Japan: JPX/TSE.
- Turkey: Borsa Istanbul/KAP where permitted for local personal use.
- Hong Kong: HKEX.
- Later: LSE and Euronext.

Acceptance:
- Clean Windows install has a non-empty US security master while offline.
- OTC and CBOE identifiers are retained in the database.
- Global reference import is collision-safe.
- Canonical US rows keep CANONICAL scope after global-reference enrichment.
- Non-US reference rows can be queried by market/exchange.

## Phase 2C — Embedded Japan / Turkey / Hong Kong Reference Seeds

Status: COMPLETE

Goal:
- Give clean Windows installs broad offline security-master coverage for the
  three priority non-US markets without requiring a paid API.

Embedded reference markets:
- Japan: JPX/TSE equities plus ETFs from the FinanceDatabase JPX export.
- Turkey: Borsa Istanbul equities plus ETFs from the FinanceDatabase IST export.
- Hong Kong: HKEX equities plus ETFs from the FinanceDatabase HKG export.

Seed behavior:
- Generated during Windows build from the current upstream MIT reference files.
- Only active/non-delisted rows are packaged.
- Yahoo-style source symbols are retained as aliases (7203.T, THYAO.IS,
  0700.HK) while the canonical local ticker is suffix-free.
- Rows are tagged REFERENCE_ONLY and cannot silently become authoritative S15.3
  model evidence.
- MIC / currency / ISIN / sector / FIGI metadata is retained where available.
- Minimum build gates: JP >= 3000 rows, TR >= 300 rows, HK >= 1500 rows.

Historical scope:
- This embedded seed is a current security-master snapshot, not multi-year
  OHLCV history.
- Price/fundamental history remains in the canonical local Parquet/SQLite data
  fabric and will be handled by later historical-pack/background-sync work.

## Phase 3 — Background Data Sync Service

Status: COMPLETE

Deliverables:
- Background scheduler separate from RUN ANALYSIS.
- Incremental universe refresh.
- Incremental price refresh.
- Incremental SEC fundamental refresh.
- Queue, retry, backoff, and bounded concurrency.
- Startup warm-up without blocking UI.

Acceptance:
- RUN ANALYSIS performs no mandatory live download when cache is warm.
- Analysis path is local and deterministic.

## Phase 4 — Free Active/Passive Provider Routing

Status: IN PROGRESS

Baseline free routing:
- Universe: SEC EDGAR primary; cached SEC snapshot passive.
- Fundamentals: SEC EDGAR authoritative; free/optional providers enrichment only.
- Prices: Stooq/local validated Parquet primary for historical use where eligible; Yahoo-compatible emergency UI fallback.
- Paid providers, if configured later, are optional accelerators only.

Acceptance:
- No API key is required for baseline startup and cached analysis.
- Missing optional API keys never fail application startup.

## Phase 5 — Two-Source Confirmation

Status: PLANNED

Deliverables:
- Critical price windows validated against a second source when available.
- Fundamental secondary-source comparison against SEC.
- Validation status stored with provenance.
- Divergence thresholds produce diagnostics, not silent blending.

Acceptance:
- Canonical source remains single-source.
- Validation differences are queryable and visible.

## Phase 6 — SEC Local Mirror + Incremental Update

Status: PLANNED

Deliverables:
- Local cache for SEC ticker universe and selected SEC JSON/XBRL payloads.
- ETag/Last-Modified aware refresh where supported.
- Incremental filing/fact ingestion.
- Respect SEC fair-access policy and User-Agent requirements.

Acceptance:
- Repeated refreshes avoid redownloading unchanged payloads.
- SEC temporary outage can use last-known-good mirror.

## Phase 7 — Async Provider Racing

Status: PLANNED

Deliverables:
- Safe parallel probes for eligible fallback/enrichment providers.
- Cancel losing requests after a valid winner is selected.
- Never race authoritative-vs-fallback in a way that weakens canonical policy.
- Per-provider concurrency limits.

Acceptance:
- Lower median refresh latency without changing canonical selection semantics.

## Phase 8 — Observability + Data Health UI

Status: PLANNED

Deliverables:
- Provider health dashboard.
- Availability, latency, freshness, error rate, rate-limit status.
- Circuit state and last success.
- Cache age / last-known-good indicator.
- Background sync status and queue depth.

Acceptance:
- A user can identify why a source is unavailable without reading logs.

## Phase 9 — Windows First-Run / Recovery Hardening

Status: PLANNED

Deliverables:
- Packaged schema verification.
- Empty security_master auto-bootstrap.
- Writable runtime verification.
- Corrupt DB recovery strategy.
- Offline-first startup path.
- Clean-install smoke test.
- Upgrade migration test.

Acceptance:
- Fresh Windows install reaches usable cached/live state without manual file copying.

## Phase 10 — Production Audit

Status: PLANNED

Deliverables:
- Full test suite.
- Network-failure simulation.
- Rate-limit simulation.
- Provider outage simulation.
- Cache corruption test.
- Windows build smoke test.
- Performance benchmark.
- Release checklist.

Target:
- Data integrity >= 9.8/10
- Availability >= 9.8/10
- Speed >= 9.7/10
- Fault tolerance >= 9.8/10
- Offline capability >= 9.7/10
