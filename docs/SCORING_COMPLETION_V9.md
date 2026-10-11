# MERİDYEN M10 — Scoring Completion V9

**Checkpoint:** V8 PR #182 at `727635e4255ca8167a09e4b874b9287dfe5361c1`; 2026-10-11. **Worktree:** isolated `E:/M10/.scoring_v9`; branch `codex/scoring-completion-v9`. **Primary outcome: TWO additional independently computed FY2025 Piotroski S9 Research scores**: INOD **55.555556** and CRMD **55.555556**. Sealed report `E:/M10/.scoring_v9_private/scoring_completion/v9_research_report.json` replays original SEC sources and all 15 V8 predecessors offline. **Total 17 full Research scores; 0 historical canonical securities/dates, 0/22 S16-C PIT features; S16-E inactive.** No extrapolation from partial accounting evidence or use of old prices as live quotes.

## 1. Five-company comparison

| Stock | S7 | S9 | S11 | S12 | New V9 fully accepted | S14 |
|---|---:|---:|---:|---:|---:|---|
| INOD | 100.000000 | **55.555556** | **0.000000** | 91.528866 | **S9 (+1)** | N/A, 3/6 |
| TMDX | 100.000000 | 77.777778 | N/A | 85.403881 | 0 | N/A, 2/6 |
| CRMD | 100.000000 | **55.555556** | 86.015359 | 95.682132 | **S9 (+1)** | N/A, 3/6 |
| PENG | 100.000000 | 66.666667 | N/A | 83.512058 | 0 | N/A, 2/6 |
| ETON | 100.000000 | 55.555556 | 7.860332 | N/A | 0 | N/A, 2/6 |

The preserved 15 Research scores are S7 five, S9 three, S11 three and S12 four. V9 adds two S9 for **S9 accepted count 5**, total **17**. INOD **S11=0.0** remains an actual accepted zero, not a missing record. Complete S14 remains N/A for all five. These are FY2025 financial-report Research inputs; none establishes historical provider access / point-in-time admissibility. Any displayed cached quote must retain its historical retrieval timestamp.

## 2. INOD S9: two original SEC long-term borrowing snapshots

**Frozen source:** original Piotroski 9-signal V7 implementation `app/scoring_v7_piotroski.py` and upstream contract source SHA `53dce841fd5ebdfeb00636f327493be1255ea8b60e6df4eadd921a7098813794`. Original gate: long-term financial borrowings / average total assets **strictly decrease**, then `S9 = 100 × positive signal count / 9`. Equality gives `F_DELTA_LEVERAGE=0`; the first eight signals were already issuer-pinned and independently replayed in V8.

**Original official filings:** INOD CIK `0000903651`, FY2025 10-K `0001104659-26-020655` filed 2026-02-26 (body SHA `2d5dd7f964d0239ea18a982f24e077d1b8e0f08baa73fd28dd66f539d9befba2`); FY2024 10-K `0001410578-25-000194` filed 2025-02-24 (body SHA `a2c0241be84173898a65f43480a16346704f6d61786e3ab4feff61886d973031`). Original SEC Companyfacts SHA `6ccc9dcc93b9c303cee51c166f345350fb16258408c884e2ed5d1231f2741b38`; original submissions SHA `070461656ae36691ad952bd53e529dd48fbb74b8f7191637d3c6bb79e27910f3`.

- The **2025 10-K Note 16** explicitly states the Wells Fargo secured revolving facility **was not utilized in FY2025** or through filing. The **original 2024 10-K Note 16** explicitly states the same for FY2024. Facility limit/borrowing base (~$30m in 2025, ~$22.3m in 2024) is undrawn capacity, not loan proceeds or balance-sheet debt.
- The **2025 10-K Note 6** enumerates total long-term obligations FY2025/FY2024 as pension **$9.278m/$7.945m** plus vendor Microsoft license liability **$0.006m/$0.442m**. Their totals are **$9.284m/$8.387m**, separating non-interest-bearing pension obligations and scheduled software/vendor payments from financial borrowing. The original FY2024 10-K Note 6 corroborates its 2024 pension/license balances.
- Original **Note 8** presents operating lease liabilities separately; a discounted operating lease commitment is not silently substituted for financial long-term debt in the original V7 S9 definition. No absent debt XBRL tag was imputed to zero: the **source evidence supporting zero** is affirmative unused revolving borrowing plus the complete identified audited liability note; other listed obligations were classified individually.

Consequently comparable **FY2025 and FY2024 long-term interest-bearing borrowing = $0 and $0** under the existing V7 scope. Therefore both positive-asset denominators produce leverage ratios **0/average assets = 0**, with **no strict improvement** (`F_DELTA_LEVERAGE=0`). All nine binary signals independently recalculated: ROA 1; CFO 1; ΔROA 0; CFO versus ROA 1; ΔLEV **0**; liquidity 1; no issuance 0; Δgross margin 1; Δasset turnover 0. Five positives yield **INOD S9 = 55.55555555555556**. The original 60-digit Decimal reference, SHA pins, year bindings and private offline report replay all pass. Private receipt: `E:/M10/.scoring_v9_private/inod_s9/report.json` plus SHA seal. Code `app/scoring_v9_inod.py`, CLI `scripts/scoring_v9_inod.py`.

## 3. CRMD S9: original cost-of-sales bridge and 2030 notes

**Original official filings:** CRMD CIK `0001410098`, FY2025 10-K `0001213900-26-023889` filed 2026-03-05 (body SHA `8c0d3d8e015ca200773b6612cb3d3e773cbedd9cc03b2bb7b58b02e56128b500`); original FY2024 10-K `0001013762-25-001852`, filed 2025-03-25 (body SHA `0e81486909c550385c08553e5c37bf7de2bbff77c5ce3fdb8f6a1a276772a52a`). The missing FY2024 original was fetched **once** from official SEC by authorized contact and stored exclusively in the new private V9 cache (HTTP 200; no repeated 403/429). Cached replay makes **zero** network requests.

| Consolidated operations, USD | FY2025 | FY2024 comparative |
|---|---:|---:|
| Revenue (`Revenues`) | $311,709,000 | $43,472,000 |
| Reported `CostOfRevenue` (excludes intangible amortization) | $22,089,000 | $3,034,000 |
| **Separate intangible amortization** (`crmd:AmortizationOfIntangibles`, inline scale=3) | **$13,872,000** | **$156,000** |
| **Original model-consistent total cost of sales** | **$35,961,000** | **$3,190,000** |
| Gross profit | $275,748,000 | $40,282,000 |

The FY2025 audited consolidated operations statement displays *cost of sales (exclusive of amortization of intangibles)* followed by the separate **amortization of intangibles** line before *gross profit*. Thus the exact unexplained V8 gaps **$13,872,000 and $156,000** are **resolved**, with source-backed custom inline extension and two-year arithmetic (`Revenue − total COGS = GrossProfit`). The original FY2024 10-K separately confirms full-dollar revenue **$43,472,170**, full-dollar total cost **$3,190,534**, gross profit **$40,281,636** (rounded comparative numbers above). This is an actual accounting bridge, not a plug or invented normalized expense.

**Long-term financial borrowing:** FY2025 audited balance sheet and Note 7 document August 2025 **$150,000,000 principal** convertible senior notes due 2030, less **$5,374,000** debt discount, net carrying value **$144,626,000**. The FY2024 original full-dollar balance sheet reconciles **$33,839,632 current liabilities + $349,091 noncurrent operating lease = $34,188,723 all liabilities**; no older financial note/loan residual. Thus comparable FY2024 long-term interest-bearing borrowings **$0**. Current debt/average assets > prior zero, so strict improvement **`F_DELTA_LEVERAGE=0`**.

**Critical SEC data error discovered:** the FY2025 balance-sheet convertible-net number uses inline `us-gaap:DeferredTaxLiabilitiesOther` with **`scale=3`** (USD $144,626,000), while the notes' `us-gaap:ConvertibleDebtNoncurrent` has **`scale=0`** despite the filing table's displayed thousands (Companyfacts reports USD $144,626). Reading the latter blindly would understate debt **1,000×**. Source-pinned audited balance-sheet + Note 7 original statement values take precedence. Convertible principal and carrying value are **not double counted**; operating leases are kept separate.

Nine original S9 binary signals CRMD: ROA 1; CFO 1; ΔROA 1; accrual 1; ΔLEV **0**; Δliquidity 0; no issuance 0; Δgross margin **0**; Δasset turnover 1. Five positives: **CRMD S9 = 55.55555555555556**. Original 60-digit Decimal high-precision independent recomputation agrees. Receipt `E:/M10/.scoring_v9_private/crmd/report.json`, SHA `fcb7c20d8ec7f01e5b554b69a12b4e3a3180860f1bdb5108e472a253bd19693f`; full bytes and sources replay offline. Implementation and 12 focused tests in `app/scoring_v9_crmd.py`, `scripts/scoring_v9_crmd.py`, `tests/test_scoring_v9_crmd.py`; [separate audit](SCORING_V9_CRMD.md).

## 4. All-model ledger

| Model | V8 full-score start | V9 concrete outcome | **New accepted full** | Unresolved mandatory evidence |
|---|---:|---|---:|---|
| S1 / S2 / S3 | 0 each | V8 research factor/gates retained; no synthetic Core/H | 0 each | Complete 48 Core, 12 Control, historical H, route/Gate6 |
| S4 / S5 | 0 each | V8 classification preserved | 0 each | Issuer-specific Beneish complete numerator/denominator, DEPI/LVGI/interaction |
| S6 | 0 | INOD 5/7; RSST aggregate 0.059140128066 candidate only | 0 | STI/LTI/DLC/DLTT classifications, Inventory and frozen partitions |
| S7 | 5 | 5 preserved | 0 | No new score needed |
| S8 | 0 | Original SHA-frozen Ohlson/Altman contract recovered; FY2024/25 SIZE numeric diagnostics on five real issuers | 0 | FFO/FUTL authentic accounting mapping, Altman full inputs/variant; vintage GNP needed for historic PIT |
| **S9** | **3** | **INOD and CRMD original FY2025 10-K evidence resolved, 9/9 each** | **2** | Five current Research S9 full; future PIT still separate |
| S10 | 0 | Original frozen Dechow–Dichev cash-flow residual/peer formula recovered; independent OLS implemented | 0 | Five annual industry×accounting-regime peer panels, future-year CFO, regression percentile and real complete cohorts |
| S11 | 3 | All original three preserved, including INOD true 0.00 | 0 | Other issuers' original minimum peers; S10 cohorts cannot substitute |
| S12 | 4 | ETON investigated, still partial diagnostic 70.19324578 | 0 | ETON FY2025 net income is nonpositive; **CCR/FCFCR positive-NI hard gates** missing, no imputation |
| S13 | 0 | 14 bodies, 27 sourced findings, 0/7 expert decisions preserved | 0 | Human signed AUD/RPT/REC/DIL/REV/ACQ/GOV materiality and serious flags |
| S14 | 0 | INOD 3/6; CRMD 3/6; others 2/6 | 0 | S6, B_Q and S13 fully accepted; original S11 zero retained |
| S15.3 V1.2 | 0 | Partial readiness retained | 0 | S15.2, M10 >=5/7, T10 >=5/7, essential-route >=70% |
| S15.3 V1.4 | 0 | Partial magnitude/fit retained | 0 | 22–24 original missing feature/gate requirements |
| S15.3 V1.4.1 | 0 | V1.2 precondition still enforced | 0 | V1.2 READY first |
| S16-C | 0 | Canonical 0/22 | 0 | Proper historical PIT provider availability and full same-date normalized universe |
| S16-E | 0 | Inactive Estimated model | 0 | Out-of-sample calibration, explicit user activation |
| S16-EA | 0 | Alert evidence remains candidates only | 0 | First publication timestamp, same-clock historic bars/events; verified alerts still 0 |

**Original frozen external source recovered in V9:** local installed private Meridyen Equity Research reference file `S1_S2_S14_CANONICAL_SOURCE.md`, SHA `53dce841fd5ebdfeb00636f327493be1255ea8b60e6df4eadd921a7098813794`, S8 lines 1325–1442 and S10 lines 1486–1544. The original paper/contract is *not changed*. S8 Ohlson SIZE uses **ln(assets in USD / preceding calendar year's GNP price index, rebased 1968=100)**, GNP annual series BEA/FRED `A001RD3A086NBEA`; official current revised 2017-base values 1968=18.246, 2023=122.361, 2024=125.496. Ten genuine issuer×FY2024/FY2025 **SIZE diagnostic** values computed; full frozen S8 also requires FFO/TL and Altman, and remains N/A. No 2024/25 as-of vintage is claimed from present-day revised series.

Original S10 uses TCA = ΔCA−ΔCash−ΔCL+Δshort-term debt, with fiscal year/industry×accounting-regime OLS on a constant and previous/current/next year operating cashflows normalized by assets; residual dispersion across five years and original peer percentile normalization. Independent four-parameter, full-rank OLS implementation and targeted CRMD historical receivables validation delivered; no synthetic five-year cohort. CRMD FY2021 source contains `AccountsReceivableNet=$45,368` (USD) from exact original 2021 10-K; FY2022/2023 remain unproved. Specific [S8/S10 accounting report](SCORING_V9_S8_S10.md).

## 5. Master Tasks 9–18 (no invented DONE acceptance)

| Master task | V9 status | Genuine new work | Remaining DONE acceptance |
|---|---|---|---|
| 9 S14 quality components | PARTIAL | INOD financial debt classification now supports S9; separate B_Q/S6 rules retained | S6 7/7, B_Q 7/7, specialist-signed S13 7/7 |
| 10 INOD full S14 | BLOCKED | V9 accepted INOD S9; S14 itself still 3/6 | B_Q/S6/S13 complete then frozen aggregate reference |
| 11 S1/S2/S3 | PARTIAL | Source readiness retained | Core48+Control12+H and all routers complete |
| 12 S15.3 | PARTIAL | Version requirements documented | V1.2 hard gates, V1.4 magnitude/fit, V1.4.1 dependency |
| 13 SEC historical PIT | PARTIAL | SEC filing source identities and dates verified for new S9 | Historical public distribution and provider availability proof, not just SEC accepted-at |
| 14 S16-C canonical | BLOCKED | 0/22 normalized features preserved | Exact PIT 22/22, historical cross-sectional universe and gate evidence |
| 15 S16-E Estimated | PENDING_APPROVAL | No production Estimated activation | Full calibration and explicit user's enablement approval |
| 16 S16-EA alerts | PARTIAL | SEC source events retained | True first-published event timestamps and same-clock replay |
| 17 five-stock comparison | PARTIAL | **17** actual Research scores on same five stocks; INOD+CRMD S9 connected | Remaining frozen model scores and source/provider gap closures |
| 18 Windows Personal Edition | PARTIAL | Isolated V9 Qt staging regression for 17 scores | Explicit user approval and production installed app acceptance |

**Master tasks with end-to-end DONE status: 0/10.** This does not erase the concrete new S9 score acceptances, original contract recovery, new verified accounting mappings or passing V9 staging. `S16-E Estimated=N/A (inactive)` and `S16-C Canonical=N/A (0/22)` remain separate.

## 6. Repeatable acceptance, Windows staging, safety and delivery

Offline original source acceptance:

```powershell
cd E:/M10/.scoring_v9
E:/M10/.venv/Scripts/python.exe scripts/scoring_v9_inod.py
E:/M10/.venv/Scripts/python.exe scripts/scoring_v9_crmd.py --verify-only
E:/M10/.venv/Scripts/python.exe scripts/scoring_v9_accept.py
E:/M10/.venv/Scripts/python.exe scripts/scoring_v9_s8_s10.py
E:/M10/.venv/Scripts/python.exe -m unittest tests.test_scoring_v9_inod tests.test_scoring_v9_crmd tests.test_scoring_v9_s8_s10 -q
```

`app/scoring_v9_report.py` independently reloads all **15 V8 original Research scores** by the existing `app/scoring_completion.load_report`, then recomputes INOD/CRMD source-pinned nine-signal results using cached 10-K bodies/SEC Companyfacts. It rejects changed receipt seals, changed source bytes, changed 9-signal counts, canonical promotion and forged cached V9 report values. `app/ui/scoring_completion_page.py` only directs the exact private V9 staging file to the dedicated V9 loader; all earlier report paths continue using their existing acceptance machinery. No installed Personal Edition or live database writes are performed. Qt offscreen staging checks 5 stocks, 15 columns, both new S9 scores, original INOD true-zero S11, S14 N/A, and zero canonical. **The staging result is not production distribution.**

**Observed Windows staging:** PASS; 5 stocks, 15 columns, 17 complete Research scores, 2 newly accepted S9 scores, INOD/CRMD each 55.555556, S11 INOD 0.0, S14 N/A, S16-C PIT 0/22, correct Qt exit and window close. Stored only under `E:/M10/.scoring_v9_private/windows_smoke/v9_acceptance1/receipt.json` with private screenshot. **Local validation:** 29/29 new V9 unit tests PASS and 42/42 affected V8/existing regression tests PASS (71 targeted tests overall); Python compilation and `git diff --check` PASS.

Independent new score evidence is sealed exclusively under `E:/M10/.scoring_v9_private/`, including original CRMD FY2024 10-K bytes. Original V1–V8 private caches/receipts, frozen formulas, main `E:/M10` worktree, installed Personal Edition 1.0.6, live `operational.db`, ~9.2GB historical database, backups, Hermes and prior PRs #170–182 are preserved. No commercial API, SEC 403/429 bypass, PR merge, EXE deployment, S13 fake signature, or historical PIT promotion. Separate user approval is still needed for S16-E production activation and installed Personal Edition deployment, and a real specialist review remains necessary for S13.
