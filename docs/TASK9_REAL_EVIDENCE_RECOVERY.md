# MERİDYEN M10 — Görev 9 gerçek finansal kaynak tamamlama

**Date:** 2026-10-11 JST. **Scope:** INOD S14 required research inputs B_Q,
S6, S11, S13. Isolated worktree `E:/M10/.task9_quality_evidence`, branch
`codex/task9-quality-evidence`, based on verified successful PR #176 commit
`e94819cb6124536bd7213de6dcf269a67e6df74f`.

## Real completion: no fabricated model scores

| Model | V3 baseline | Task9 evidence delivered | Whole real score |
|---|---|---|---|
| B_Q | Five of seven Beneish risk legs | Verified FY2024/25 debt facility not used; extracted **company-specific** XBRL long-term obligations and reconciled pension-vs-license split, checked approximate PPE D&A (not pure depreciation). | **N/A**, 5/7 risk legs |
| S6 Dechow | Four of seven mathematical components | Original Dechow `ISSUE` definition is 1 when any debt/equity issuance; FY2023/24/25 **stock option exercises issued actual new shares for cash**, confirmed from exact SEC Companyfacts tag and audited 10-K statement of stockholders' equity. **ISSUE=1**, 5/7 total. | **N/A**, RSST/Δ inventory not source-verifiable |
| S11 Modified Jones | INOD 8/8 verified accounting values, 0/20 dated industry peers | Historical FY2025 **SEC SGML 10-K headers established SIC=7374**; independent 20 peer cohort passed original model. 547 candidates screened, 23 financially complete prechecks, 20 contemporaneously industry-proven and accepted. Distinct independent high-precision Decimal OLS also passed. | **0.000000/100, REAL_SCORE_ACCEPTED_RESEARCH**, not N/A |
| S13 forensic | 14 actual SEC filing bodies, zero risk decisions | Re-extracted **27 substantive, multi-clause source-matched contexts** in all seven AUD/RPT/REC/DIL/REV/ACQ/GOV blocks. Exact SEC accession and source-content SHA for each; independent flags held unknown, not zero. | **N/A, REVIEW_REQUIRED**; 0/7 signed rubric decisions |
| S14 aggregator | S7=100; S12=91.528866 | Real S11 **0/100** is the third actual normalized component; frozen formula unchanged. Remaining B_Q/S6/S13 mandatory. | **N/A, 3/6** |

**NEW full issuer Research model scores accepted: 1 (INOD S11=0.00).** Prior nine complete genuine S7/S12
research submodel outputs across INOD, TMDX, CRMD, PENG and ETON unchanged.
New five-stock total: **10** real full research model scores; full S14 still N/A.
Historical canonical securities 0, accepted historical dates 0.

## 0. First real source-complete S11 — independent Jones computation

**INOD FY2025 original SEC accession:** `0001104659-26-020655`, accepted
`2026-02-26T22:22:13Z`. Original 10-K SGML filing header recorded historical
SIC **7374**; header evidence SHA256
`7d401ccbbf67f76aba8541bd5473de5f91025654e65b541a003d3d21dc6fcde6`.
No current Submissions SIC is backdated as a historical fiscal classification.

Real cohort via official SEC SIC directory (548 unique CIKs), existing
SEC bulk Companyfacts ZIP (20,440 CIK files), SEC 10-K acceptance and original
header classification: **547 independent candidate issuers screened**;
23 passed exact eight-input FY2025 XBRL financial precheck; **20 different SEC
CIK issuers** passed the sector-year fiscal-period and filing-header industry
conditions. Six contemporaneous FY2025 10-K/A cases were separately reviewed
for Part III-only amendments and unchanged financial fields; company identity,
filing/source times, period, and 45-day fiscal window were enforced. 20/20
qualified minimum. Rank-3 real OLS, no fabricated coefficients.

| Modified Jones SEC source calculation | Result |
|---|---:|
| OLS alpha1 | -245159.9552498829 |
| OLS alpha2 | -0.37477873832369635 |
| OLS alpha3 | -2.364961328421979 |
| FY2025 scaled total accrual | -0.12843656621036764 |
| Nondiscretionary accrual (NDA) | -0.3753663997395018 |
| Discretionary accrual (DA) | +0.24692983352913417 |
| Original absolute fallback threshold | 0.20 |
| **Normalized REAL S11 Research score** | **0.000000 / 100** |

The score is genuine zero rather than `None`: the unchanged original fallback
`100*max(0,1-|DA|/0.20)` clips at 0 because `|DA|=0.24693`. This is a quality
risk indication, **not a demonstrated accounting manipulation or fraud claim**.
Source formula: `app/recovered_jones.py`, original model spec SHA
`53dce841fd5ebdfeb00636f327493be1255ea8b60e6df4eadd921a7098813794`,
lines 1550–1623. The independent Decimal 3x3 OLS solver (normal equations),
separate from source QR method, confirmed coefficients, NDA/DA and final score;
maximum relative coefficient discrepancy about 1.43e-15.

Final private reproducible cohort receipt:
`.../runtime/scoring_completion/task9_jones/reports/task9_jones_20261010T190029504391Z.json`,
SHA256 `7dd64041a65013cc7f95ebdc35198f65c95810680b45b68f11e54eea7938d6e0`.
Final offline replay used only existing private SHA-verified SEC response bytes,
**0 additional SEC HTTP requests**. Source availability at current research
date is proven; historical first-publication/provider PIT timing is NOT proven.
**S11 is COMPLETE_RESEARCH, not historical canonical.**

## 1. S6 — actual three-year equity issuance recovered

| Fiscal year | Positive cash proceeds from stock options exercised | `ISSUE` | Filing evidence |
|---|---:|---:|---|
| FY2023 | USD 3,324,000 | 1 | FY2024 10-K accession `0001410578-25-000194` |
| FY2024 | USD 6,668,000 | 1 | FY2025 10-K accession `0001104659-26-020655` |
| FY2025 | USD 3,331,000 | 1 | FY2025 10-K accession `0001104659-26-020655` |

SEC tag: `us-gaap:StockIssuedDuringPeriodValueStockOptionsExercised`, `USD`,
full annual flow, accepted within source filing. Confirmed both exact original
Companyfacts records and the audited consolidated statement of stockholders'
equity with the same cash exercise amount (filing statements in USD thousands).
**Positive verified cash issuance**, not the SBC expense, authorized but unsold
ATM stock, or mere share-count movement. `ISSUE=1` applies to the original
Dechow debt/equity issuance indicator; no code/formula revision or zero default.

The remaining S6 model needs exact three-year reviewed WC/NCO/FIN RSST
decomposition and an independently evidenced inventory change. The two annual
10-Ks do **not** disclose a suitable signed inventory balance or explicit
zero-inventory assertion. The frozen normalization's ambiguous endpoints and
extreme bin remain fail-closed; no arbitrary percentile or missing-value fill.

## 2. B_Q DEPI: real note, but not pure depreciation

2025 10-K Note 3, "Property and equipment" cites approximately USD **2.2m**
PPE-related **depreciation and amortization** for FY2025 and USD **1.5m**
for FY2024. 2024 10-K Note 3 additionally cites USD **1.2m** for FY2023.
The audited total cash-flow D&A amounts are distinct and incorporate intangible
assets and capitalized software; its `us-gaap:DepreciationDepletionAndAmortization`
cannot be substituted for the pure depreciation input required by DEPI.
`inod:` extension `DeferredTaxAssetsDepreciationAndAmortization` and
`DeferredTaxLiabilitiesDepreciationAndAmortization` are *tax assets/liabilities*,
not depreciation expense. Separate source proof for pure depreciation and its
aligned capitalized-software treatment is still missing. **DEPI=N/A**.

## 3. B_Q LVGI: actual XBRL extension debt-type reconciliation

Official FY2025 10-K Note 6, "Long-term obligations", and exact source
inline XBRL `inod:` extension tags identify three different liability groups:

| Amount (USD thousands) | FY2024 | FY2025 | Meaning |
|---|---:|---:|---|
| Accrued pension obligations | 7,945 | 9,278 | **Not borrowing** |
| Microsoft license obligations | 442 | 6 | Vendor service/software contract; interest-bearing classification unproven |
| Total long-term obligations | 8,387 | 9,284 | **NOT total interest-bearing debt** |
| Current long-term-obligation portion | 1,643 | 1,659 | Includes pension/contract balances |
| Non-current portion | 6,744 | 7,625 | Includes pension/contract balances |

Two reconciliations passed from independently extracted `ix:nonFraction` rows:
`9,278+6=9,284` and `1,659+7,625=9,284` for FY2025, analogously
`7,945+442=8,387` and `1,643+6,744=8,387` for FY2024. Units are thousands
(`scale=3`), `unitRef` USD, `contextRef` exact instant fiscal December 31 date.
Tags: `inod:CurrentPortionOfLongTermObligations`,
`inod:NoncurrentPortionOfLongTermObligations`,
`inod:TotalLongTermObligations`, `inod:MicrosoftLicensesObligations`.

Both FY2024 Note 17 and FY2025 Note 16 expressly say the Wells Fargo
**revolving credit facility was unused** during each respective fiscal year.
An unused USD30m borrowing **capacity** is not debt. Software license
installments are separately evidenced but not proven to be interest-bearing;
pensions must not be counted as financial leverage. Consequently comparable
positive interest-bearing balances for both years **are NOT established** and
an unjustified zero prior-year denominator cannot be repaired. **LVGI=N/A**.

## 4. S13 source context, no invented human judgment

Fourteen original SEC filing bodies are SHA-256 validated (two 10-K, two
10-Q, nine 8-K and one 8-K/A). 27 actual corroborated contextual passages:
AUD 4; RPT 4; REC 4; DIL 4; REV 3; ACQ 3; GOV 5. Findings distinguish:

- FY2025 auditor's revenue-recognition CAM **versus** misstatement or fraud.
- FY2025 one customer 63%/$29.2m receivables and FY2024 two customers
  61%/$16.6m receivables **versus** actual loss/deficiency.
- August 2026 up-to-$300m ATM authorization **versus** actual share sales.
- FY2024–25 10-K related-party Item 13 incorporated-by-reference proxy
  requirement; one named officer's 8-K Item404 no-transactions assertion
  **versus** company-wide transaction absence.
- SEC/DOJ information requests and securities allegations **versus** confirmed
  findings; CEO/CFO/board transitions **versus** proof of governance failure.

**0/7 signed/numeric risk-block rulings**; serious flag independence still
unknown (`null`, not zero). The original recovered 0/25/50/75/100 rubric
requires source-specific materiality/independence judgments. Do not activate
S13 until those decisions are independently reviewed and recorded. Task9
extractor is a reviewer-ready, current-research packet—not a claimed human
forensic audit or a score.

## Source identity and private receipts

- Official SEC Companyfacts, CIK 903651: SHA256
  `6ccc9dcc93b9c303cee51c166f345350fb16258408c884e2ed5d1231f2741b38`.
- Official FY2024 10-K HTML: SHA256
  `a2c0241be84173898a65f43480a16346704f6d61786e3ab4feff61886d973031`.
- Official FY2025 10-K HTML: SHA256
  `2d5dd7f964d0239ea18a982f24e077d1b8e0f08baa73fd28dd66f539d9befba2`.
- `.../runtime/scoring_completion/task9_financial_extension1/financial_recovery.json`
  sealed source evidence SHA256
  `21e932ed4862173373bafa7214c09f5c71dc0b387b9bb64f24250fd6355169c7`.
- `.../runtime/scoring_completion/task9_forensic/review_v1.json`
  sealed human-review **request packet**, SHA256
  `a61cf29c59a3e0f095f29835037e08b935997e048591c1b0bc87b66b0cf38355`.
- Frozen original S1/S14 source SHA256
  `53dce841fd5ebdfeb00636f327493be1255ea8b60e6df4eadd921a7098813794`.

SEC links: `https://www.sec.gov/Archives/edgar/data/903651/000110465926020655/inod-20251231x10k.htm`,
`https://www.sec.gov/Archives/edgar/data/903651/000141057825000194/inod-20241231x10k.htm`.
Full bodies and private receipts stay under `%LOCALAPPDATA%` **outside Git**.

## Engineering, acceptance and safety

- `app/task9_financial_recovery.py` source-joins annual cash exercise,
  reconciles inline XBRL pension vs software license and accrued obligations,
  retains missing DEP/RSST/INV flags, no financial-score fabrication.
- `app/task9_forensic_review.py` original-filing contextual source verifier
  (27 findings); no automatic risk/serious-count.
- `app/scoring_completion.py` verifies source bytes + SHA-sealed Task9 receipts,
  offline replays original methods, and explicitly attaches `S6_ISSUE=1` to
  the existing INOD S6 evidence coverage (4/7 → **5/7**). S6/S14 numeric null.
- `app/task9_jones_acceptance.py` independently replays actual 20-issuer
  SEC SIC-year qualification and OLS from the private SEC cache before
  promoting **S11=0.0**. `load_report` repeats this replay when displaying a
  score from the sealed research report. Score zero is correctly treated as a
  *complete* score in count and UI, while frozen S14 stays 3/6 and N/A.
- Windows Qt research comparison now shows 5 stocks / **14 columns** (S11
  score explicitly at the top of the table); exposes
  source evidence in read-only details, S6 5/7, B_Q 5/7, **S14 3/6**,
  S11 0.00 explicitly in its model table, and **10** full research model scores.
- No Main checkout, Personal Edition, live DB, backup, frozen S15/S16,
  Hermes or previous PR modified. All new files in isolated task9 branch.

**Task9 DONE condition is NOT MET** because B_Q/S6/S13 are incomplete,
although a real first new full S11 score, verified historical issuance and
27 contextual forensic records are completed. Source-pinned model contracts,
missing/null vs zero semantics, and individual research vs canonical status
remain distinct.
