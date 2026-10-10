# MERIDYEN M10 — Faz 28 Real Scoring Completion Engine V1.0

**Result:** 28A/B feature engineering DONE; **first independently evidenced complete S1–S16 model score: 0 / BLOCKED**; staging Windows research integration DONE; Personal Edition **NOT UPDATED**.

This is a current-research quality and gap audit, not an historical PIT acceptance, an unapproved independent S4–S13/S16-E model, investment advice, a new distribution or a user-approved version installation.

## 28A — source base

- GitHub PR chain **#170 → #171 → #172**, latest checked Phase27 HEAD **d031307**; Phase27 Python CI **SUCCESS** before branching Phase28.
- Phase28 code isolated in branch `codex/phase28-real-scoring`, separate worktree `E:/M10/.phase28_real_scoring`; original `E:/M10` unchanged.
- Phase27 verified private file `%LOCALAPPDATA%/S153ResearchTerminal/runtime/phase27/current_scoring/staging.db` is read-only to Phase28; INOD original 251 daily Yahoo-compatible OHLCV, last trade **2026-10-09T20:00:01+00:00**, **USD 62.04** and local cached SEC financial period **2026-06-30** are re-used, **no repeat network download**. Other four Phase27 ticker stage results are not re-fetched because no first full INOD score has passed.
- A prior independently verified 9.2GB archival **copy** `%LOCALAPPDATA%/MeridyenM10Personal/historical_readonly/operational.phase26b.snapshot.db` is a **read-only** supplementary source for equity, assets and working-capital metrics. Phase28 never connects to the original production operational DB.
- **Actual official SEC retry:** one properly identified request to `https://data.sec.gov/api/xbrl/companyfacts/CIK0000903651.json`, HTTP **403**, response HTML (4,818 bytes), **no retry or bypass**. SEC_USER_AGENT user-specific contact environment was absent, provider default identifies repo URL; use a legitimate contact user-agent with SEC fair-access compliance if future permission/access allows. Independently verified SEC `accepted_at` fields remain absent in INOD cached source. **No direct-SEC canonical score accepted.**

## 28B — genuinely derived INOD evidence

**Storage:** new `%LOCALAPPDATA%/S153ResearchTerminal/runtime/phase28/real_scoring_v1/stage.db` (Phase28-only schema marker). Data source queries use read-only SQLite URI + `query_only`, and new stage refuses existing unknown SQLite, paths outside a resolved `phase28` folder, symlinks and `operational.db` names. Phase27 staging SHA-256 matched **before and after** the live Phase28 INOD calculation.

Each feature carries actual `value`, `unit`, `period_end`, `as_of`, `available_at`, `source`, `source_ref`, `license_scope=LOCAL_PRIVATE_RESEARCH_ONLY`, `quality_status=RESEARCH_ONLY_ACCEPTED_AT_UNVERIFIED`, `computation_version`, `evidence_hash`, and original accession/source-hash inputs. Future timestamps, non-10-K/Q forms, period-future and missing/bad SHA are rejected. All quoted financial values are USD unless explicitly marked ratio or shares.

| INOD researched feature | Real calculation | Condition / caveat |
|---|---:|---|
| Last quote | **$62.04** | Yahoo-compatible last trade 2026-10-09 20:00:01 UTC; not live bid/ask |
| Calendar 2025 revenue YoY | **+47.64%** | 2024 vs. 2025 full annual figures from local SEC-origin cache |
| 2026 Q2 revenue YoY | **+57.80%** | Exact year-over-year Q2 periods |
| 2026 Q2 sequential revenue | **+2.27%** | 2026 Q2 vs. Q1; exact quarter interval |
| INOD 2026 Q2 net margin | **15.64%** | Same reported quarter numerator/denominator |
| TTM revenue to 2026-06-30 | **$317.164m** | 2025 annual + 2026 H1 YTD − 2025 H1 YTD |
| TTM net income | **$46.485m** | Same exact fiscal-window roll-forward |
| TTM FCF | **$183.848m** | Roll-forward operating cash flow minus capex; may include nonrecurring customer advances / working-capital effects |
| Current-price × 2026-07-31 shares | **$2.1331bn** | Dated SEC cached shares × Yahoo last trade; **market-cap research estimate**, not official current float |
| P/S from TTM revenue | **6.73×** | Estimate based on dated shares/current last trade/uncertified cached SEC periods |
| P/E from TTM net income | **45.89×** | Same qualification; not a live vendor valuation |
| FCF yield on estimated market cap | **8.62%** | Cash conversion could be distorted by customer advances; not a quality score |

**36 distinct** Phase28 INOD feature records were derived and saved after the current evidence filters. Output precision beyond reported rounding is not a statement of economic accuracy. ROE (half-year, average equity when available), working capital, current ratio, share dilution and SBC/revenue were also computed from matching periods; EV/EBITDA, canonical ROIC, short interest, contemporaneous spread, float, and industry benchmark values remain N/A where input evidence is insufficient. Cached facts with `accepted_at=NULL` **remain RESEARCH_ONLY**, even if their original `source_document` says SEC.

### Proven frozen-rubric *subcomponents*, not full model scores

| Frozen existing calculation | INOD value | Input coverage |
|---|---:|---|
| 1Y revenue-growth normalization, `D01` first leg only | **97.05 / 100** | Year-on-year revenue; missing other D01 legs |
| 1Y EPS-growth normalization, `D02` first leg only | **8.43 / 100** | Dated annual diluted EPS; missing other D02 legs |
| Revenue acceleration `D03` leg | **0.00 / 100** | Exact 3 consecutive annual revenue records, existing acceleration rubric |
| Dilution quality `F54_DIL` leg | **45.28 / 100** | Approximately one-year dated share counts, existing dilution rubric |

The original `core48`, `control12`, `dna60` functions can calculate **partial-math diagnostics** with N/A weight renormalization; the available coverage is **3/48 discovery** and **1/12 control** only. Partial DNA is **NOT** a completed verified DNA60 vector, a complete S1/S2/S3 value, or an accepted canonical prediction; the UI only exposes it in tagged detail.

## 28A/C/D — exact verified full-score readiness for INOD

| Model | Independently qualified mandatory model inputs | Missing / strict blocker | Full score |
|---|---|---|---|
| **S1** | **0/4** final components | Complete qualified DNA60, router, historical H winner/control, N61 risk | **N/A** |
| **S2** | **0/4** final components | Complete DNA60, Gate6, historical H, false-positive penalty | **N/A** |
| **S3** | **0/3** final components | Complete DNA60, router, historical H | **N/A** |
| **S4–S5** | No independently frozen scoring specification | `SPEC_MISSING` | **N/A** |
| **S6–S13** | Referenced within S14/company quality; independent 0–100 spec not verified | `SPEC_MISSING` as standalone model, cannot infer subscore from accounting ratios | **N/A** |
| **S14** | **0/6** qualified normalized legs | `B_Q`, `S6`, `S7`, `S11`, `S12`, `S13` (and independent rubrics for each) | **N/A** |
| **S15.3 V1.2** | No fully accepted gate family | 48 discovery, 12 control, router/market-cap scenario, historical H, magnitude/time and other route-dependent features | **N/A** |
| **S15.3 V1.4** | No fully accepted gate family | Frozen V1.2 upstream & V1.4-specific route/scenario requirements | **N/A** |
| **S15.3 V1.4.1** | No fully accepted gate family | Frozen V1.2 + V1.4 features, route-confidence/assumption-burden and related gates | **N/A** |
| **S16-C V1.0** | **0/22** independently accepted PIT-normalized inputs | 22 frozen S16 feature keys, missing float/short/news/catalyst/social/normalized volume/risks etc. | **N/A** |
| **S16-E** | **No approved numeric contract** | Separate proposed draft **not activated**, `SPEC_MISSING` | **N/A** |
| **S16-EA V1.3** | No verified event/intraday anchors | Genuine 1m/5m bars, UTC news event and same-clock baselines | **N/A** |

S15.3 per-route **exact number of mandatory raw inputs is UNVERIFIED**; its audit lists six *missing gate families*, **not** falsely claims it has only six normalized input fields. Existing frozen model versions are included in the local `scored_models` table. Frozen S1–S16 formulas, penalties, weights and gates have **not** been modified or relaxed. A complete input contract will yield a numeric full model score only after *every required normalized input* is independently supported.

## 28E — Estimated S16 design

`docs/PHASE28_S16_E_ESTIMATED_DESIGN_DRAFT.md` is the proposed S16-E architecture (1–5 session horizon, real OHLCV, volume/liquidity, independently time-stamped float/short/catalyst/social and risk evidence, missing-data policy, calibration, PIT controls). **No new numerical S16-E weighting, default/penalty or coverage threshold has been approved or activated**. The draft is not S16-EA.

## 28F — pilot scope

Only **INOD** was recomputed in Phase28, obeying the first-complete-score gate; there was no refetch of the four other equities.

The already-successful Phase27 **cached price audit** remains:

| Ticker | Last verified phase27 research price, USD | S1 | S2 | S3 | S14 | S15.3 V1.2 | S15.3 V1.4.1 | S16-E | S16-C |
|---|---:|---|---|---|---|---|---|---|---|
| **INOD** | **62.04** | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| **TMDX** | **77.87** | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| **CRMD** | **7.38** | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| **PENG** | **76.28** | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| **ETON** | **55.21** | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |

All prices above are Phase27 **2026-10-09 last-trade snapshots**, not a repeat Phase28 live-market test. **Five** equities previously had verified research OHLCV; **one** (INOD) underwent Phase28 added financial/contract analysis; **zero** independently accepted complete S1–S16 model scores.

## 28G–H — engineering/test evidence

- Existing `app/ui/phase27_current_page.py` reused (not a new application); Phase28 read-only status and sourced evidence overlays the existing 20-row model matrix **only** if `M10_PHASE28_STAGING_DB` points to a recognized Phase28 stage with matching ticker+price time. Otherwise prior Phase27 behavior remains. No automatic provider request. Selected row shows missing normalized legs and original evidence source; research and historical canonical are kept separate.
- Real Windows Python 3.11 + Qt offscreen main window loaded the existing **7 tab** GUI and the **INOD 36-feature Phase28 overlay**. No new EXE/installer built because user explicitly requested avoiding redundant package cycles; existing Windows Personal Edition files remain intact.
- **15/15 focused synthetic software regression tests PASSED**: Phase27 (8) plus Phase28 (7). Phase28 tests include exact period math, missing/forbidden source SHA, zero fake scoring, 22 PIT S16 gates, staging DB refusal before DDL, immutable source proof, idempotent isolated output, and UI model drilldown; these synthetic tests are **not** counted as actual stock-score successes.
- Current Phase28 INOD real pilot: **1/1 financial-feature investigation**, **36 derived research features**, **20 separate model audits**, **0 accepted complete scores**.
- No automatic PR merge, production SQL migrations, live app install, Hermes edits, frozen-model code edits, new API keys or paid-source acquisitions.

**Concurrent-data caveat:** during this separate session the original operational DB `%LOCALAPPDATA%/S153ResearchTerminal/runtime/data/runtime/operational.db` showed a last-write change **from 2026-10-10 20:49:46 local to 2026-10-11 01:23:10 local**, and its length increased by 24,576 bytes. Phase28 code opens only Phase27 stage read-only, independently protected archival research copy read-only and its own Phase28 stage; the source of this concurrent original DB change was **not identified**. Personal app process was running and was **not terminated**. Thus no claim is made that external systems were globally immutable.

## Phase28 independent To-Do — don't merge with the historical 27 tasks

- [x] ~~28A: Confirm PR #172 and create separate worktree/branch from latest d031307.~~
- [x] ~~28A: Reconcile exact mandatory S1/S2/S3/S14 and S16-C feature contracts and S4–S13 SPEC_MISSING gaps.~~
- [x] ~~28B: Reuse verified Phase27 251-bar INOD and research SEC cache **without a new market-data download**.~~
- [x] ~~28B: Implement period-matched INOD revenue/net/FCF/working-capital/dilution/TTM cash-conversion features with evidence, timestamps and original SHA.~~
- [x] ~~28B: Run one ethical direct-SEC check (403), record gap, no bypass.~~
- [x] ~~28C: Execute *actual frozen subcomponent functions* and record their observed input coverage separately from final model scores.~~
- [x] ~~28D: Full-model fail-closed scoring and evidence matrix: clear missing fields, S14, S15.3 route gates and all S16-C 22 features.~~
- [x] ~~28E: Create S16-E **unapproved** design with no active estimator.~~
- [x] ~~28G: Reuse existing Windows research UI with offline Phase28 source/score detail overlay.~~
- [x] ~~28H: Targeted original Phase27 + new Phase28 regression suite, live Windows Qt stage smoke, independent staging source SHA check.~~
- [ ] **BLOCKED — FIRST COMPLETE STOCK MODEL SCORE:** normalized standalone S14 quality-rubrics or S1–S3 historical H/complete controls must be established and independently evidenced. No model score may be labeled complete yet.
- [ ] **BLOCKED — OFFICIAL SEC ACCESS:** HTTP 403 and null `accepted_at` prohibit independently authoritative historical PIT facts.
- [ ] **BLOCKED — S16-C:** 22 required PIT normalized attributes not accepted. Independent float/short/news/options/social and cross-sectional price normalization required.
- [ ] **BLOCKED — Phase28 full five-security extension:** user required **first complete INOD model score** before scaling. Stage27 baseline available, not refetched.
- [ ] **PENDING USER APPROVAL — S16-E activation:** proposed independent numeric estimation formula/weights/risk gates and confidence policy need explicit version acceptance.
- [ ] **PENDING USER APPROVAL — PERSONAL UPDATE:** no overwrite of installed personal app or its active DB.
- [ ] **PENDING REVIEW — Phase28 PR/CI** tracked separately; historical canonical master To-Do untouched.

## Priority to get the FIRST FULL SCORE

First, source an **independent, documented and frozen mapping** for the S14 0–100 legs `B_Q/S6/S7/S11/S12/S13` rather than assuming raw company ratios satisfy them. Alternatively, obtain valid winner/control historical similarity `WINNER_SIM/CONTROL_SIM` plus full DNA/router/risk controls for S3/S1/S2. Only after an exact formula-input evidence chain has no missing fields should the frozen scorer run with a real final numeric value. Price/financial extraction alone is **not** a full scoring pass.

**Unchanged historical acceptance:** Canonical **0 securities / 0 security-dates**, WF9 **BLOCKED**, Learning V3 **NOT_TRAINED**. This does **not** invalidate completed current-research engineering work.
