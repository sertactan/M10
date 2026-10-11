# MERİDYEN M10 — V11 original-score acceptance audit

**11 October 2026 (JST).** Isolated branch `codex/scoring-completion-v11` from V10
commit `331b6131e3c3627219f3986a9d80c99ff23923ad`. This is a Research
audit, not a historical PIT calculation. Frozen source SHA-256 remains
`53dce841fd5ebdfeb00636f327493be1255ea8b60e6df4eadd921a7098813794`.
No frozen formula, accepted score, private SEC body, database, executable or
other worker's checkout was changed.

## A. Accepted complete Research scores

| Issuer | S6 | S7 | S8 | S9 | S10 | S11 | S12 | B_Q | S14 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| INOD | N/A | 100.000000 | N/A | 55.555556 | N/A | **0.000000** | 91.528866 | N/A | N/A |
| TMDX | N/A | 100.000000 | N/A | 77.777778 | N/A | N/A | 85.403881 | N/A | N/A |
| CRMD | N/A | 100.000000 | N/A | 55.555556 | N/A | 86.015359 | 95.682132 | N/A | N/A |
| PENG | N/A | 100.000000 | N/A | 66.666667 | N/A | N/A | 83.512058 | N/A | N/A |
| ETON | N/A | 100.000000 | N/A | 55.555556 | N/A | 7.860332 | N/A | N/A | N/A |

**V11 new complete scores: 0; cumulative complete scores: 17.** S7 5, S9 5,
S11 3 and S12 4 are preserved. INOD S11 zero is a genuine complete score.
CRMD's FY2025 $144,626,000 convertible classification and original 2025/2024
amortized-cost bridge remain as accepted in V9; this audit does not recast them.

## B. ETON S6 — primary-statement findings and hard stop

Issuer CIK `0001710340`; FY2024 original 10-K accession
`0001437749-25-008136`; FY2025 original 10-K accession
`0001437749-26-009059`. Original 10-K statements display **USD thousands**;
the independently pinned Companyfacts records used by V10 are **USD**.

| Classification | FY2023 | FY2024 | FY2025 | Evidence and acceptance decision |
|---|---:|---:|---:|---|
| Current debt (DLC), net carrying value | $5.380m | $0m, printed dash | $8.789m | Explicit current portion of long-term debt on the original balance sheets; do not mix with accrued liabilities. |
| Noncurrent debt (DLTT), net carrying value | $0m, printed dash | $29.811m | $21.769m | Explicit noncurrent debt row; debt discounts and accrued fees affect its carrying value. |
| Stock option exercise cash proceeds | $0.149m | $1.191m | $0.598m | FY2025 filing's three-year cash-flow statement; its equity statement independently records 2025 $0.598m and 321,083 shares in the combined options/RSU-vesting row. The option note separately identifies 161,933 option-exercise shares for 2025. `ISSUE=1` has stronger direct primary-statement corroboration. |
| Short-term and long-term investments (STI/LTI) | Unresolved | Unresolved | Unresolved | Neither balance sheet prints a separate investment row or explicit zero. Cash equivalents include short-term money-market funds, while other-current-asset and other-long-term-asset captions exist. Absence of a separate line does not establish zero STI/LTI under the original RSST classification. |
| Preferred equity (PREF) | Unresolved | Unresolved | Unresolved | The balance sheets print common stock and no preferred-equity amount; the charter permits future undesignated preferred issuance. Authorization is not issuance, but no explicit three-year preferred outstanding reconciliation was source-bound. |

The 2025 filing shows current/noncurrent operating lease liabilities separately
from loan debt and identifies inventory-purchase/vendor obligations under
accounts payable and other long-term liabilities. They cannot silently enter
DLC/DLTT. V10's algebraic RSST aggregate
`-0.110320559686632548...` and conditional `F_D=1.49893572492284258...`
replay exactly at 65-digit Decimal precision; they **do not** independently
validate the three WC/NCO/FIN partitions. The frozen source defines RSST as
`(ΔWC+ΔNCO+ΔFIN)/AverageAssets` but does not supply a complete classifier
for every modern SEC account. An explicit classifier, source-bound STI/LTI/PREF
amounts and independently reviewed partition are still necessary. The
original primary 10-K HTML bytes were read from SEC online but were not
locally sealed for offline byte replay. Accordingly **ETON S6 = N/A**, reason
`DATA_MISSING` for financial investment/preferred classification and primary
body hash, plus `REVIEW_REQUIRED` for the accounting partition. The 70 bin
remains a diagnostic, not an accepted score.

Primary sources: [ETON FY2025 10-K](https://www.sec.gov/Archives/edgar/data/1710340/000143774926009059/eton20251231_10k.htm),
[ETON FY2024 10-K](https://www.sec.gov/Archives/edgar/data/1710340/000143774925008136/eton20241231_10k.htm).
The V10 sealed Companyfacts receipt is
`E:/M10/.scoring_v10_private/extension_s6/eton_s6_candidate_v1.json`, SHA-256
`523c8d48babf4c080e1bef13e3b74d308d4e4ba682a8c6ad4c0bce656e5e321d`.
This V11 review adds primary-statement corroboration; it does not claim the
online statement excerpts have a local byte seal.

## C. Model acceptance and next real-source work

| Model | V10 full | V11 full | New | Exact remaining gate |
|---|---:|---:|---:|---|
| ETON S6 | 0 | 0 | 0 | STI/LTI/PREF classification, separately reviewed WC/NCO/FIN, sealed original 10-K bytes; re-evaluate frozen normalization after final inputs. |
| B_Q / S5, CRMD/ETON/PENG | 0 | 0 | 0 | Original eight Beneish terms and interaction must all use comparable exact periods; `TOTAL_DEBT` scope for LVGI and any zero denominator require an original-rule decision. Pure DEPI receipts replay: CRMD 0.761229684221, ETON 5.328106852497, PENG 1.069471644355. DEPI alone is no B_Q score. |
| S8 | 0 | 0 | 0 | Original Ohlson `funds provided by operations` cannot yet be reconstructed equivalently from the five FY2025 GAAP reports: `ORIGINAL_DEFINITION_UNRECONSTRUCTABLE` on current evidence. CFO/EBITDA substitutions require a separately versioned and approved model. INOD conditional Z'' 7.7074978776 still lacks an accepted EBIT and equity-policy bridge; manufacturer market equity must match fiscal-end date. Prior GNP/1968-base and SIZE work remains valid as current revised-series diagnostics, not PIT vintages. |
| S10 | 0 | 0 | 0 | Five original SIC × accounting-regime annual peer panels and complete target CFO boundaries. FY2025-centered residuals require unavailable FY2026 annual CFO. FY2020–24 is a possible fully elapsed window under the frozen rule, but needs FY2019 opening accounts, FY2025 lead CFO, five panels and defined sigma/percentile conventions. CRMD FY2022/23 TCA $2,285,613/$14,315,240 are design rows only. |
| INOD S6/B_Q/S13/S14 | 0 | 0 | 0 | INOD S6 remains 5/7 with its own inventory and partition gaps; B_Q 5/7 lacks pure depreciation and original `TOTAL_DEBT` LVGI. If matched borrowing is genuinely 0/0, record `SPEC_EDGE_CASE`. S13 remains unsigned 0/7 (`REVIEW_REQUIRED`); S14 remains 3/6. |
| TMDX/PENG S11 | 0 | 0 | 0 | Offline original dated peers remain 12/20 and 1/20; no reduced-minimum regression. |
| S1–S3 / S15.3 | 0 | 0 | 0 | Core48/Control12/Historical H and route gates; S15.2/M10/T10, fit and version prerequisites. No new source overcomes them here. |
| S16-C / S16-E / S16-EA | 0 | 0 | 0 | Canonical 0/22 normalized PIT features; Estimated remains OFF pending OOS calibration and separate user approval; early warning lacks first-publication and same-clock OHLCV replay. |

Original Ohlson reference: [Ohlson (1980), *Journal of Accounting Research*](https://doi.org/10.2307/2490395).
Decision package A retains frozen S8 and N/A; package B would create an
explicitly versioned modern-accounting adaptation only after user approval.
No approval for B is inferred here.

The new offline `scripts/scoring_v11_beneish_inventory.py` checks exact
FY2025 10-K accession, CIK, pinned original SEC Companyfacts bytes, USD unit,
annual window and both fiscal periods for each proposed Beneish fact. It
re-verifies the existing pure DEPI result and does not calculate a complete
score. The exact-tag inventory found these unresolved **candidate tags**:

| Issuer | Missing exact tag candidates in both periods | Interpretation |
|---|---|---|
| CRMD | `RevenueFromContractWithCustomerExcludingAssessedTax`, `SellingGeneralAndAdministrativeExpense`, `LongTermDebtCurrent`, `LongTermDebtNoncurrent` | Search actual filing-specific revenue/SGA/debt presentations; absent tag is not zero or proof of absent economic amount. |
| ETON | `CostOfRevenue`, `SellingGeneralAndAdministrativeExpense` | The 10-K prints cost of sales and operating-expense rows, but their concepts and scope need exact mapping. Debt candidate tags exist; original `TOTAL_DEBT` scope remains unaccepted. |
| PENG | `CostOfRevenue` | Original cost-of-sales concept needs filing-specific mapping; August fiscal boundaries remain distinct. |

This makes the next B_Q retrieval issuer-specific instead of repeating DEPI.
No zero-denominator convention, alternative concept or serious flag was
inferred from the inventory. Its output is an exact-source diagnostic, not
an accepted model receipt.

## D. Master Tasks 9–18

| No. | State | Verified sub-work | Still required for DONE |
|---:|---|---|---|
| 9 | PARTIAL | ETON issuance/debt statement corroboration; three pure DEPI components retained. | S6 and B_Q full gates, signed seven-category S13 review. |
| 10 | BLOCKED | INOD three genuine S14 limbs unchanged. | S6, B_Q and S13, then independent geometric S14. |
| 11 | PARTIAL | Prior source inventories retained. | Actual Core48, Control12, Historical H and route acceptance. |
| 12 | PARTIAL | Prior versioned diagnostics retained. | S15.2, M10/T10, model fit and each version prerequisite. |
| 13 | PARTIAL | Exact original filing accessions retained. | Dissemination/available-at history and as-of replay. |
| 14 | BLOCKED | 0/22 S16-C features. | Dated universe/provider availability, 22/22 PIT normalized features. |
| 15 | BLOCKED | S16-E remains OFF. | Independent OOS calibration and separate explicit activation approval. |
| 16 | PARTIAL | Prior source inventory retained. | First-publication timing and same-clock historical OHLCV. |
| 17 | PARTIAL | Five-stock 17-score comparison preserved. | Missing original model acceptances. |
| 18 | PARTIAL | V11 isolated Windows Qt staging replay passed: 5 stocks, 15 columns, 17 full scores. | Full final acceptance and separate deployment approval. |

**DONE: 0/10.** The only current price previously staged was the dated
9 October 2026 close; no live quote is asserted in V11.

## E. Verification and boundaries

V10 exact offline source replay in the V11 checkout: ETON S6 receipt **PASS**,
Beneish DEPI quality receipt **PASS**, S10/S11 peer inventory **PASS** with zero
network requests. Windows scoped V10 private-source tests: **43/43 PASS**.
The independent V11 Beneish exact-tag inventory completed successfully. V11
Windows Qt offscreen staging **PASS**: five stocks, 15 columns, 17 original
complete Research scores, S16-C 0/22 and no production window installation.
These are source and component checks; none passes a complete new model.
The V10 PR #184 is still draft/open at the exact baseline SHA, and its
[Python CI run](https://github.com/sertactan/M10/actions/runs/38134303546)
completed successfully. Public CI cannot read Windows private SEC caches;
cache-dependent tests there are **SKIP**, not private-source PASS.

No live `operational.db`, historical database, installed Personal Edition
1.0.6, backup or earlier worktree was written. No S16-E activation, PR merge,
expert signature or production install was attempted. The distinct human
decisions remaining are S13 authorized review, potential versioned S8
adaptation, S16-E activation and final Personal Edition deployment.
