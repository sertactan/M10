# MERİDYEN M10 — Phase 27A–27J Current Stock Research Pilot

**Disposition: REAL_DATA_INGEST_DONE / RESEARCH_COMPONENTS_DONE / FULL_MODEL_SCORING_BLOCKED / STAGING_WINDOWS_UI_DONE.**
This is an **isolated research implementation**, **not** a Personal Edition update, production deployment, canonical acceptance, or completed historical backtest.

## 27A — Git and source inventory

Source: `codex/phase27-current-scoring` branched from GitHub PR #171 HEAD `5b3dcda` (PR #170 → PR #171 → Phase27). Separate Windows worktree: `E:/M10/.phase27_current_scoring`. Original `E:/M10`, existing Personal Edition install, Phase26A/B/C backups and Hermes untouched. Initial Personal Edition database read **only**: `canonical_model_features=0`, `fundamental_facts_source=0`; provider/cache status does **not** imply completeness from past reports.

Independent model formula inventory from actual code:

| Model | Definition in repository | Current pilot result |
|---|---|---|
| S1 | `core/scoring/s1_s14.py:s1`, DNA60/router/H/N61 | N/A, `INCONCLUSIVE`; historical winner/control similarity and other complete legs absent |
| S2 | `s2`, DNA60/Gate6/H/false-positive penalty | N/A, `INCONCLUSIVE`; source-backed 0–100 legs absent |
| S3 | `s3`, DNA60/router/H | N/A, `INCONCLUSIVE` |
| S4–S5 | No independent frozen callable/spec verified | `SPEC_MISSING` as independent model |
| S6–S7 | Referenced as required S14 *component fields*, not verified independent frozen scorers | `SPEC_MISSING` as independent model |
| S8–S10 | Used by `company_quality` composition; independent full model not verified | `SPEC_MISSING` as independent model |
| S11–S13 | Referenced as S14 input legs; no independent frozen callable verified | `SPEC_MISSING` as independent model |
| S14 | `s14`, earnings quality geometric mean, conflict and forensic penalties | N/A; B_Q/S6/S7/S11/S12/S13 incomplete |
| S15.3 V1.2 | `S153V12Model`; Core48/Control12/DNA60, routers, destination, M10 and T10 | N/A `INCONCLUSIVE`; no qualified canonical input set |
| S15.3 V1.4 | `S153V14Model`, frozen V1.4 source | N/A pending full upstream V1.2 and route/scenario evidence |
| S15.3 V1.4.1 | `S153V141Model`, `S15.3_V1.4.1_CANONICAL_COMPLETION_2026-10-07` | N/A; upstream V1.2 + missing route/confidence components |
| S16-C | `S16V1Model`, 22 PIT features `S16_REQUIRED_FEATURES` | **0/22** independently accepted, N/A |
| S16-E | No approved/versioned independent Estimated 0–100 scorer discovered | `SPEC_MISSING`, N/A; **not** replaced with S16-EA |
| S16-EA V1.3 | Separate event/news-triggered model | N/A; true 1m/5m bars, same-clock baselines and primary event timestamps missing |

**No S1–S16 weights, formulas or canonical inputs were modified.** `core/scoring/s1_s14.py`, `core/models/s153_v12.py`, `core/models/s153_v141.py`, `core/models/s16.py` remain untouched. The model matrix calls the frozen models with **missing** unverified features, **never** hidden zero/50/default substitutions.

## 27B–C — Genuine live-endpoint research and isolated SQLite

- **INOD FIRST:** actual Yahoo-compatible HTTPS `v8/finance/chart/INOD` responded HTTP **200** with valid symbol `INOD`, currency `USD` and exactly **251 dated daily OHLCV/adjusted-close observations** for one-year window. Last transaction trade date 2026-10-09; `regularMarketTime` 2026-10-09T20:00:01Z; last provider price 62.04 USD. **Last trade, not verified exchange streaming/current bid/ask.**
- Direct official SEC Companyfacts (`data.sec.gov`) returned **HTTP 403**. No evasion, private credential/session scrape, rate-limit rotation, or claimed new SEC canonical acceptance. Stooq US daily endpoint HTTP 200 response was **HTML**, not a valid requested CSV, so it was not promoted to price data.
- The **previous independently verified Phase26B local SEC cache** was inspected through the user's preserved 9.2 GB read-only historical research copy using SQLite URI `mode=ro&immutable=1` / `PRAGMA query_only=ON`. Cached SEC-derived facts include period, filing date, accession, `available_at`, source and SHA. In sampled INOD 2026-Q2 fact, `accepted_at=NULL` and `available_at=2026-08-07` is a *derived availability date*, **not an independently verified SEC filing acceptance timestamp**. Consequently all such local data is labeled `SEC_EDGAR_LOCAL_ARCHIVE_ACCEPTED_UNVERIFIED`, **RESEARCH_ONLY_NOT_CANONICAL_PIT**. Cached financial data was copied only as selective rows into the new Phase27 staging DB; neither original archive nor Personal DB were written.
- Staging destination, not tracked in Git: `%LOCALAPPDATA%/S153ResearchTerminal/runtime/phase27/current_scoring/staging.db`. Schema `M10_PHASE27_CURRENT_RESEARCH_V1`; typed `stock_runs`, `research_bars`, `research_facts`, `research_features`, `model_audits`. A pre-existing SQLite without a matching stage marker is rejected **before DDL**, as are symlinks and paths without a resolved `phase27` directory.
- 251 real dated OHLCV per security, **1,255 total bars**, **6,541 unique** research-cached SEC fact rows, **100 persisted research features** and **100 per-model audit rows** across five tickers. An earlier prototype briefly overcounted NULL-period SEC duplicates; a **stage-only normalized unique index** and dedup migration removed those duplicates, and a synthetic retry regression test now enforces it. No fact rows or prices were pushed to GitHub. All price rows include source, observed-at, URI and payload SHA-256. Derived features include separate `as_of` vs. `available_at`, quality, version, source reference and evidence hash. No accepted-at timestamp is silently guessed.
- Original 0–100 **growth component** uses frozen `app/feature_materializer.py` `GROWTH_KNOTS` / `_score_growth`. Numbers from that specific research leg are **not full S1/S2/S14/S15/S16 model scores**. Other genuine raw research features: OHLCV, 20/50/200 SMA, 20-day RVOL, volatility, 5-session momentum, turnover trend, exactly matched quarter-over-quarter revenue, matched-period gross/net/operating margin, annual revenue CAGR when years are consecutive, exact-window CFO minus capex, and last price × separately dated SEC cached shares as a **research-only market-cap estimate**. No unverified SEC growth/margin is promoted to canonical PIT. Missing float/short/gamma/social/catalyst/quality inputs remain missing.

## 27D–G — Five real pilots (2026-10-09 US close / market timestamp in stage)

The INOD pilot's actual quote/fundamentals/feature status was verified **before** querying the four other requested securities.

| Symbol | Last Yahoo-compatible USD | Dated daily OHLCV | Current research features | Latest cached SEC financial period | Matched-quarter revenue YoY | Current complete S1–S16 score |
|---|---:|---:|---:|---|---:|---|
| INOD | 62.04 | 251 | 19 | 2026-06-30 | +57.80% | **N/A** |
| TMDX | 77.87 | 251 | 21 | 2026-06-30 | +20.70% | **N/A** |
| CRMD | 7.38 | 251 | 20 | 2026-06-30 | +156.52% | **N/A** |
| PENG | 76.28 | 251 | 19 | 2026-05-29 | N/A (no verified matching year-over-year quarterly comparison) | **N/A** |
| ETON | 55.21 | 251 | 21 | 2026-06-30 | +98.59% | **N/A** |

Additional **period-matched research raw** observations (not scoring confirmations):

| Ticker | Sequential revenue QoQ | Same-quarter net margin |
|---|---:|---:|
| INOD | +2.27% | 15.64% |
| TMDX | +9.21% | 7.73% |
| CRMD | -20.01% | 25.50% |
| PENG | +39.57% | 9.34% |
| ETON | +54.90% | 30.80% |

Latest quote timestamps are 2026-10-09 20:00:00–20:00:01 UTC from provider metadata. A **4-calendar-day freshness heuristic** recognizes the Friday close over a Sunday; it does not turn the delayed/last trade data into a live exchange quote. Refuse future dates, wrong ticker/currency, duplicate trading dates and invalid OHLCV. A provider failure is `PROVIDER_ERROR`; out-of-window data is `STALE_DATA`. Empty dataset remains `MISSING_DATA`/`INCONCLUSIVE`. Request attempts are bounded: one Yahoo-compatible HTTPS request with 12-second request timeout; no infinite retries. The terminal has a separate offline **LOAD CACHED** mode with no network calls.

**Exact S16-C required 22 and current missing 22:** `market_cap_scarcity, float_scarcity, short_pressure, float_turnover, liquidity_elasticity, ownership_lock, catalyst, volume_ignition, momentum_acceleration, social_velocity, news_velocity, regime_sympathy, attention, compression, catalyst_proximity, theme, anomaly, dilution_risk, extension_risk, data_risk, liquidity_risk, manipulation_risk`. No approved S16-E contract, so S16-E N/A rather than made-up estimated scoring. SEC 403/cached filings alone cannot cure that.

**Acceptance counts:** Genuine-price securities **5/5**; successful complete full-model scores **0/5**; independent model audits **100/100 saved**; 0 false canonical claims; 0 synthetic results presented as real data. Missing required evidence is explicitly listed for each model and ticker.

## 27F/H — Separate Windows implementation and tests

- `app/ui/phase27_current_page.py`: opt-in **S1–S16 CURRENT RESEARCH** tab, interactive ticker input, separate asynchronous bounded fetch, last price/time/finance period, 20 model rows with score/status/coverage and expandable click-to-see exact missing feature/source diagnostics. `LOAD CACHED (offline)` never makes a network request.
- `app/ui/main_window.py` adds that tab **only** if `M10_PHASE27_STAGING_DB` is set, with an explicit separate `M10_PHASE27_HISTORICAL_ARCHIVE` read-only source. Previous installed Personal app unchanged.
- `scripts/phase27_research_pilot.py` allows a bounded one-symbol staging fetch or `--offline` stored-report display. It requires an explicit archive for online runs; no hidden production DB fallback.
- `tests/test_phase27_current_scoring.py` uses **synthetic fixtures only as regression tests**, never passed off as real prices or scores: **8/8 PASS**. Cases include symbol/currency, future timestamp, stale provider, provider 429 with retention of previously valid offline cache, S16 22-feature score gate, non-Phase27 SQLite write rejection, NULL fiscal-period duplicate prevention, source read-only preservation and offscreen Qt table/score detail.
- Real Windows Qt staging run verified 7-tab main window, INOD 62.04 panel, 20 model rows, click-to-source details, open/close. Real separate Windows PyInstaller **exit 0**, Python 3.11, Windows PE FileVersion/ProductVersion `1.0.6.0`, **10,924,950 bytes**, SHA-256 `4D70963BC903B94C06A4F41B77B6AD671138C180560C23B30029CAD64D19191C`, Authenticode `NotSigned`; packaged seed manifest `PRIVATE_TEST_ONLY` passed verification. Package was produced in isolated `%LOCALAPPDATA%/S153ResearchTerminal/runtime/phase27/windows_current_1060_run2`; real Windows `--doctor` **exit 0** and GUI open/WM_CLOSE **exit 0**. This is only a private **staging test build**; source refinements after build start require a reproducible final build before it can be considered an install candidate.
- The Windows source-level Qt stage acceptance also passed after those refinements. **No existing Personal Edition installed file or DB updated**, no PR merged, no EXE/seed/price files uploaded.

## 27I–J — independent engineering To-Do (separate from historical 27-item master)

- [x] ~~27A: Verify Git chain #170 → #171 and create separate branch/worktree.~~
- [x] ~~27A: Inventory frozen models and distinguish non-independent S4–S13 / estimated S16-E spec gaps.~~
- [x] ~~27B: Prove real INOD Yahoo-compatible 251 OHLCV and explicitly fail direct SEC/Stooq invalid responses.~~
- [x] ~~27B/27C: Read cached SEC-derived financial facts only in read-only local archive and record missing accepted_at as noncanonical.~~
- [x] ~~27C: Implement isolated Phase27 typed staging SQLite, identity/price/finance provenance, feature hashes and growth/momentum components.~~
- [x] ~~27D/27E: Invoke frozen full-model gates without synthetic inputs; give 20 per-stock model audit rows, include S16-E vs S16-C vs S16-EA separation.~~
- [x] ~~27G: Five real ticker OHLCV/feature/data quality pilots after verified INOD success (5/5).~~
- [x] ~~27F: Implement opt-in asynchronous Windows research tab with drill-down and offline cache.~~
- [x] ~~27H: Eight focused unit/GUI regression tests, real Qt UI and isolated Windows staging EXE/doctor/close acceptance.~~
- [ ] **PARTIAL: Full S1–S16 score readiness.** No complete frozen model currently has the required independently sourced feature set, no approved S16-E estimate spec. Do not mark these DONE until independently verified.
- [ ] **PARTIAL: Official SEC source fresh acceptance timestamps.** Direct `data.sec.gov` returned 403; proper identification/rate etiquette and approved alternate source needed, not evasion. Local filings are bounded to older cached research evidence.
- [ ] **PARTIAL: Independent license/redistribution authority and canonical adjusted/PIT price validation.** Yahoo-compatible values are current **research** OHLCV only.
- [ ] **PARTIAL: Rebuild/finalize latest-source Windows Personal Edition install candidate.** Stage private EXE is a test artifact; no user-approved update over existing personal app.
- [ ] **PARTIAL: True S16 22 PIT features, intraday 1m/5m source, historical winners/controls, qualitative and 12-control score normalizers.**
- [ ] **PARTIAL: GitHub PR + CI review and isolated final handoff**, tracked separately.

The original historical master To-Do still has **1 DONE / 9 PARTIAL / 13 BLOCKED / 4 original labels unrecovered**. This does not cancel the independently DONE Phase27 tasks above.

**Immutable baseline:** Canonical **0 securities / 0 dates**, **WF9 BLOCKED**, **Learning V3 NOT_TRAINED**. Historical 2024–25 backtest and trained learning are **not** prerequisites for Phase27 research data retrieval, but neither has become valid from the current quote stream.
