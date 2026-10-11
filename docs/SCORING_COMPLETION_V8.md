# MERİDYEN M10 — Scoring Completion V8

**Checkpoint:** V7 PR #181, `7af654a05b2c7c6ce466f4248403f48323b306c7`, 2026-10-11. **Scope:** isolated `E:/M10/.scoring_v8` branch, five current Research issuers, no production deployment. **Result:** 15/15 accepted complete Research submodel scores preserved; **0 new accepted complete scores**; **0 canonical securities/dates** and **0/22 accepted S16-C PIT-normalized historical features**. Failed model gates remain `N/A`; a partial signal count is never a complete-model score.

## 1. Exact five-stock Research comparison

| Issuer | S7 | S9 | S11 | S12 | V8 additional complete scores | S14 |
|---|---:|---:|---:|---:|---:|---|
| INOD | 100.000000 | N/A (**8/9 signals evidenced**) | **0.000000** | 91.528866 | 0 | N/A, 3/6 |
| TMDX | 100.000000 | 77.777778 | N/A | 85.403881 | 0 | N/A, 2/6 |
| CRMD | 100.000000 | N/A (**7/9 signals evidenced**) | 86.015359 | 95.682132 | 0 | N/A, 3/6 |
| PENG | 100.000000 | 66.666667 | N/A | 83.512058 | 0 | N/A, 2/6 |
| ETON | 100.000000 | 55.555556 | 7.860332 | N/A | 0 | N/A, 2/6 |

The 15 accepted observations are 5 S7, 3 S9, 3 S11 and 4 S12. A verified binary signal can be zero, and **INOD's exact S11 score is zero**, not missing. These values are independently revalidated by the original V7 `load_report` against existing sealed official SEC receipts when producing the V8 private staging snapshot. Original V7 S9 positive signal counts remain **TMDX 7/9, PENG 6/9, ETON 5/9**. Their nine input gates were all evaluated; these counts describe positives, not missing fields. No market price in this report is claimed to be current/live.

## 2. S9 original filing and precise missing-input audit

The V7 Piotroski calculator `app/scoring_v7_piotroski.py`, original source SHA-256 `53dce841fd5ebdfeb00636f327493be1255ea8b60e6df4eadd921a7098813794` and `100 × positives / 9` normalization are unchanged. The new source-bound audit uses its strict `_entry` selector, signed SEC Companyfacts and submission accession/form/period bindings, fiscal-year comparative records, pinned official 2025 10-K HTML hashes, individual fact filing dates, 60-digit Decimal calculations, and an independently sealed offline receipt replay. The original V7 calculator remains the authority for an eventual **complete** S9 score. The current incomplete V8 candidates are not promoted.

| Issuer | SEC FY2025 accession / report date | SEC FY2024 accession / report date | Verified binary signals | Missing contract gates | Result |
|---|---|---|---:|---|---|
| INOD (CIK 0000903651) | `0001104659-26-020655`, 2025-12-31, filed 2026-02-26 | `0001410578-25-000194`, 2024-12-31, filed 2025-02-24 | 8/9 | Fully sourced, comparable FY2025/FY2024 long-term interest-bearing debt classification for F_DELTA_LEVERAGE | **N/A**, no new score |
| CRMD (CIK 0001410098) | `0001213900-26-023889`, 2025-12-31, filed 2026-03-05 | `0001013762-25-001852`, 2024-12-31, filed 2025-03-25 | 7/9 | FY2024 comparable debt and complete non-overlapping FY2025/FY2024 mapping; original tagged COGS versus filed gross profit bridge for F_DELTA_GROSS_MARGIN | **N/A**, no new score |

INOD eight observed signals: `F_ROA=1`, `F_CFO=1`, `F_DELTA_ROA=0`, `F_ACCRUAL=1`, `F_DELTA_LEVERAGE=null`, `F_DELTA_LIQUIDITY=1`, `F_NO_COMMON_EQUITY_ISSUANCE=0`, `F_DELTA_GROSS_MARGIN=1`, `F_DELTA_ASSET_TURNOVER=0`. The 2025 SEC filing's `DirectOperatingCosts` agrees exactly with revenues minus gross profit for both FY2025 and FY2024 (USD **251,663,000 − 152,184,000 = 99,479,000**; **170,461,000 − 103,387,000 = 67,074,000**). Pension liabilities and software license obligations reported in the issuer filing are **not** silently classified as interest-bearing long-term debt, and absent long-term loan tags are **not** automatically zeros.

CRMD seven observed signals: `F_ROA=1`, `F_CFO=1`, `F_DELTA_ROA=1`, `F_ACCRUAL=1`, `F_DELTA_LEVERAGE=null`, `F_DELTA_LIQUIDITY=0`, `F_NO_COMMON_EQUITY_ISSUANCE=0`, `F_DELTA_GROSS_MARGIN=null`, `F_DELTA_ASSET_TURNOVER=1`. Its FY2025 `CostOfRevenue` **USD 22,089,000** is **USD 13,872,000 below** revenues less reported gross profit; its FY2024 tag is **USD 156,000 below** that bridge. Using the concept blindly would change the original gross-margin ratio. Companyfacts supplies a FY2025 `ConvertibleDebtNoncurrent` observation but no accepted comparable FY2024 debt mapping. Current gross-profit direction is diagnostic, not a frozen verified cost input; the score remains absent.

Pinned cached SEC ZIP member SHA-256: INOD `6ccc9dcc93b9c303cee51c166f345350fb16258408c884e2ed5d1231f2741b38`; CRMD `b75757faacc84388fbe591a3ec2593969ffefe3c9ea86056a188a6fcb0c2f8bb`. Pinned original current 10-K bodies: INOD `2d5dd7f964d0239ea18a982f24e077d1b8e0f08baa73fd28dd66f539d9befba2`, CRMD `8c0d3d8e015ca200773b6612cb3d3e773cbedd9cc03b2bb7b58b02e56128b500`. These official sources and private sealed evidence **stay outside GitHub**. CRMD current 10-K was fetched under configured legitimate SEC fair-access contact to the private cache without bypassing or retrying restrictions. The script otherwise replays cached sources without HTTP. V8 S9 private receipt: `E:/M10/.scoring_v8_private/piotroski_audit/source_pinned.json` plus SHA seal; V8 15-score report: `E:/M10/.scoring_v8_private/scoring_completion/v8_source_pinned_report.json` plus SHA seal.

## 3. S8, S10 and remaining S1–S16 model acceptance

| Model | V7 opening complete Research count | V8 result | Accepted total score count | Exact open blocker |
|---|---:|---|---:|---|
| S1–S3 | 0 each | Partial source/routing gates catalogued | 0 each | Full Core48, Control12, Historical H, routing/false-positive risk and frozen component normalization |
| S4/S5 | 0 each | Issuer-specific DEPI/LVGI missing conditions retained | 0 each | Pure depreciation, comparable interest-bearing debt, seven Beneish/interaction inputs and full source binding |
| S6 | 0 | INOD 5/7, partial RSST candidate `0.059140128066` | 0 | Independently classified STI/LTI/DLC/DLTT and inventory; no absent-data zero |
| S7 | 5 | All five preserved | **5** | No V8 regression; historically PIT-ineligible |
| S8 Ohlson | 0 | 12/12 **diagnostic** FY2024/FY2025 SEC GAAP fields per issuer | 0 | Official dated original GNP SIZE deflator/base convention, FFO accounting and frozen S8 inputs |
| S9 Piotroski | 3 | INOD 8/9 and CRMD 7/9 **verified signals, not completed scores** | **3** | Long-term debt mappings on both; CRMD full COGS reconciliation |
| S10 historical | 0 | Four issuers 35/35, CRMD 32/35 **diagnostic** FY2021–2025 GAAP fields | 0 | Dated five-year eligible S10-specific peer panels, exact frozen residual/regression; CRMD missing 2021–23 receivables tags |
| S11 | 3 | INOD genuine zero, CRMD and ETON maintained | **3** | TMDX and PENG need eligible peer counts; other candidates not auto-promoted |
| S12 | 4 | INOD/TMDX/CRMD/PENG unchanged | **4** | ETON acceptance criteria incomplete |
| S13 Forensic | 0 | 14 original SEC bodies, 27 contextual findings protected, 0/7 signed decisions | 0 | Qualified expert AUD/RPT/REC/DIL/REV/ACQ/GOV materiality, serious flag and duplicate-event decisions |
| S14 | 0 | INOD and CRMD 3/6; TMDX, PENG and ETON 2/6 | 0 | Complete accepted B_Q, S6, S13, then frozen geometric aggregation |
| S15.3 V1.2 | 0 | Replayed incomplete frozen gate requirements | 0 | S15.2; M10 >=5/7; T10 >=5/7; essential-route coverage >=70% |
| S15.3 V1.4 | 0 | 22 missing requirements (PENG 24) | 0 | Magnitude/route and feature evidence completeness |
| S15.3 V1.4.1 | 0 | V1.2 prerequisite enforced | 0 | V1.2 READY and independent version gates |
| S16-C | 0 | 0/22 normalized PIT features | 0 | Historical admissible provider as-of, cross-sectional normalization/22 frozen feature gates |
| S16-E | 0 | Disabled; separate Estimated status | 0 | Real-data calibration and explicit user activation authorization |
| S16-EA | 0 | SEC event candidates remain Research-only; 0 verified alerts | 0 | First-publication timestamps, same-clock historical replay and verified intraday market/session evidence |

Detailed source/member dates and SHA pins for S8/S10 are in `docs/SCORING_V8_S8_S10_AUDIT.md`. The actual S8 diagnostic completeness **does not imply Ohlson economic feature completeness**. S10 35/35 is only an inventory of seven GAAP concept families over five years, **not** five successful peer regressions. Per-company S1/S15.3 missing gates and S14 coverage counts are in `docs/SCORING_V8_OTHER_MODELS.md`. V8 did not infer the original frozen external model subsections missing from Git, nor substitute CPI or S11 cohorts into S8 or S10.

## 4. Master Task 9–18 closure table

| Main task | V8 observed status | Remaining condition to mark DONE |
|---|---|---|
| 9 — Accounting/forensic S14 components | PARTIAL | Officially classify S6 inventory/RSST and B_Q DEPI/LVGI; sign expert S13 seven-part review |
| 10 — INOD first full S14 | BLOCKED | S6, B_Q, S13 complete and independently replayed; run original frozen S14 aggregation |
| 11 — S1/S2/S3 | PARTIAL | 48/48 Core, 12/12 Control, H, router/gates with official sources and reference recomputation |
| 12 — S15.3 versions | PARTIAL | V1.2 prerequisites, V1.4 magnitude/route inputs, V1.4.1 dependency and acceptance |
| 13 — SEC and historical PIT | PARTIAL | Verify historical public dissemination and provider availability separately from SEC acceptance time |
| 14 — S16-C Canonical | BLOCKED | 22/22 PIT-normalized source-specific features, currently **0/22** |
| 15 — S16-E Estimated | PENDING_APPROVAL | Calibrate real-data estimated engine and obtain explicit user enablement approval |
| 16 — S16-EA alerts | PARTIAL | Source-first publication dates, same-clock true historical replay and eligible OHLCV/session sources |
| 17 — five-issuer comparison | PARTIAL | Extend verified full S1–S16 scoring; preserve source time, missing reasons, Research/PIT separation |
| 18 — Windows Personal Edition | PARTIAL | V8 isolated Qt staging regression and separate explicit production deployment/installed app acceptance |

**Scope and controls:** Existing V1–V7 SEC caches and source receipts, frozen contracts, historical ~9.2GB database, live `operational.db`, installed Personal Edition 1.0.6, all other worktrees, user backups and Hermes were untouched by these V8 changes. SEC 403/429 bypass, synthetic historical samples, paid APIs, unauthorized production writes, merging PRs and deployment were excluded. V7's Python CI was previously successful; V8 CI status must be verified on the new PR separately.

## 5. Validation and delivery

Run using existing Windows virtual environment from `E:/M10/.scoring_v8`. These commands use real original private inputs for the receipt replay, not mocked scoring:

```powershell
E:\M10\.venv\Scripts\python.exe scripts/scoring_v8_s9_audit.py --receipt E:/M10/.scoring_v8_private/piotroski_audit/source_pinned.json
E:\M10\.venv\Scripts\python.exe scripts/scoring_v8_accept.py
E:\M10\.venv\Scripts\python.exe scripts/scoring_v8_s8_s10.py
E:\M10\.venv\Scripts\python.exe -m unittest tests.test_scoring_v8_s9_audit tests.test_scoring_v8_s8_s10 tests.test_scoring_v8_model_gates -q
```

The V8 source-pinned S9 audit has **8/9 INOD** and **7/9 CRMD** verified signal flags, all remaining flags explicitly `null`; independent SHA and offline report replay PASS. The complete V7 receipt `load_report` source replay and V8 sealed private report returned `RESEARCH_ONLY_STAGING_SEALED`, `full_model_count=15`, `new_full_research_scores=0`, canonical 0 and S16-C accepted 0/22. The 28 focused V8 standard-library unit tests passed after pinning; broader regression and Qt smoke test acceptance belong to the final staging record. Production release remains subject to separate user approval.
