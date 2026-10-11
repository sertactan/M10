# MERİDYEN M10 — Scoring Completion V10, independent frozen S8 evidence

**2026-10-11 JST.** Clean Windows worktree `E:/M10/.scoring_v10`, branch
`codex/scoring-completion-v10`, original base `389c83a` (V9). Scope: only
`app/scoring_v10_s8.py`, `scripts/scoring_v10_s8.py`,
`tests/test_scoring_v10_s8.py`, this document, and private
`E:/M10/.scoring_v10_private/s8` receipts. Frozen formulas, existing Research
scores, live databases, EXE and previous worktrees were not changed.

## Decision

**No defensible new complete S8 score for INOD, TMDX, CRMD, PENG or ETON.**
All five remain **N/A**. This pass does produce *real original-10-K source
values*, an exact issuer-specific frozen **Altman** partial-factor calculation,
and an independently computed **60-digit Decimal Ohlson non-FFO contribution**
for every company. No complete Altman Z, Ohlson O, O_Q or S8 number was
accepted or substituted into production. All results are Research-only, not
historical point-in-time financial or market measurements.

## Frozen source and original S8 design

The originally installed `Meridyen Equity Research` plugin v0.28.1 file
`S1_S2_S14_CANONICAL_SOURCE.md` was checked **in its original private
location**; SHA-256
`53dce841fd5ebdfeb00636f327493be1255ea8b60e6df4eadd921a7098813794`
matches V9 and its integrity manifest. S8 lines approximately 1325–1442:

* Public manufacturer: `Z = 1.2 WC/A + 1.4 RE/A + 3.3 EBIT/A +
  0.6 market_equity/TL + 1.0 sales/A`.
* Nonmanufacturer alternative: `Z'' = 6.56 WC/A + 3.26 RE/A +
  6.72 EBIT/A + 1.05 book_equity/TL`.
* `O = −1.32 −0.407 SIZE +6.03 TLTA −1.43 WCTA +0.0757 CLCA −1.72
  OENEG −2.37 NITA −1.83 FUTL +0.285 INTWO −0.521 CHIN`, and
  `O_Q = 100 × (1 − logistic(O))`.
* Frozen `S8 = WA(Z_Q, O_Q)`, default 50/50. Altman Z_Q published
  original knots, frozen FFO mapping and authoritative underlying evidence
  must each pass before claiming a full score; missing is N/A.

The historical Ohlson definition describes `FUTL = funds provided by
operations / total liabilities` (Ohlson 1980, *Journal of Accounting
Research* 18(1), pp.109–131,
[DOI 10.2307/2490395](https://doi.org/10.2307/2490395)). This is **not
equivalent by default** to modern `NetCashProvidedByUsedInOperatingActivities`
(CFO), or REITs' NAREIT FFO. Published applications operationalize it in
different ways: `income before extraordinary items + depreciation (PI+DP)`,
and other specifications add deferred tax or adjust depreciation for equity
ownership. See independent [historical banking/accounting research](https://citeseerx.ist.psu.edu/document?doi=be16968adc06518d31819e5ce72c77a89fa298e0&repid=rep1&type=pdf),
[HKIMR methodology](https://www.aof.org.hk/docs/default-source/hkimr/working-papers/full-text2b6708eff7ea44109a67c823b65122cf.pdf?sfvrsn=148d4c30_0),
and [Swedish House of Finance adjusted O-score work](https://arc.hhs.se/download.aspx?MediumId=4912).
The latter explicitly discusses problems reproducing the 1980 FFO from
modern US GAAP. Another methodology documents pretax income + depreciation
as a *substitute*, not a certified equivalent. No owner-approved frozen
equivalence/issuer cash-flow reconciliation was found in the original
contract or existing receipt. Therefore **FUTL remains N/A for all five**.

## SEC filing evidence, exact annual year 2025

Only the **five already V8/V9 hash-pinned original SEC Companyfacts ZIP
members** were read. The parser requires each selected row's exact FY2025
10-K accession, issuer fiscal year end, USD, and an original annual
period of 330–400 days (or matching instant). Original filing record hashes
and specific US-GAAP tags, along with V9 source receipts, remain in the
private V10 report. The FY2025 original header SIC records for TMDX, CRMD,
PENG and ETON are reused only from the *SHA-sealed V6 research receipts*;
INOD SIC7374 is the prior research mapping and its local header is not
independently replayed in V10.

| Ticker | FY2025 period end | FY2025 SIC | Altman candidate | Filed 2025 NI, USD | Reported 2025 combined D&A, USD | Ohlson SIZE from V9 |
|---|---|---:|---|---:|---:|---:|
| INOD | 2025-12-31 | 7374 | nonmanufacturer Z'' | 32,181,000 | 6,889,000 | 12.409500 |
| TMDX | 2025-12-31 | 3845 | public-manufacturing Z | 190,291,000 | 27,185,000 | 14.255905 |
| CRMD | 2025-12-31 | 2834 | public-manufacturing Z | 163,055,000 | **combined D&A N/A** | 13.998779 |
| PENG | 2025-08-29 | 3674 | public-manufacturing Z | 25,391,000 | 56,216,000 | 14.670464 |
| ETON | 2025-12-31 | 2834 | public-manufacturing Z | −4,601,000 | 4,044,000 | 11.805039 |

CRMD's exact FY2025 source has **pure `Depreciation` $677,000** and
`AmortizationOfIntangibleAssets` **$13,872,000**, *separate* accounting
concepts; their simple sum is not a filed combined D&A figure and does not
prove complete FFO. PENG's separate depreciation $20,579,000 and intangible
amortization $35,600,000 sum to $56,179,000, **$37,000 less** than the
filer's original `DepreciationDepletionAndAmortization` $56,216,000; neither
set of concepts is casually substituted. ETON has combined D&A $4,044,000,
separate depreciation $41,000 and amortization $4,003,000. The existing
source-specific Beneish DEPI work is separate from Ohlson FFO.

The current V9 GNP SIZE deflator remains: official BEA/FRED annual GNP
deflator `A001RD3A086NBEA`, **2017=100**, normalized to **1968=100**
using 1968=18.246, 2023=122.361 and 2024=125.496 and previous calendar
year; these are 2026-revised research observations **without historical
vintage proof**. V10 independently re-performs all five FY2025 SIZE
values with 60-digit Decimal logs and rejects disagreement with V9.

### Dated equity value ≠ original cover-page public float

The SEC filing cover-page `dei:EntityPublicFloat` is a real datum with a
**different valuation date**, not the Altman market-equity value at the
FY2025 balance-sheet date. The dated observations in these FY2025 10-Ks are:

| Ticker | Cover-page public float valuation date | Frozen Altman required date |
|---|---|---|
| INOD | 2025-06-30 | 2025-12-31 (Z'' uses independently classified book equity) |
| TMDX | 2025-06-30 | 2025-12-31 |
| CRMD | 2025-06-30 | 2025-12-31 |
| PENG | 2025-02-28 | 2025-08-29 |
| ETON | 2025-06-30 | 2025-12-31 |

Even verified FY2025 shares outstanding do not establish a same-date
verified FY-end market price. There is **no dated FY-end market-equity
receipt** in the restricted input. Original four public manufacturing
Z models therefore cannot be completed. Their missing verified EBIT and
required shares × same-session unadjusted close also block acceptance.
For INOD Z'', sourced stockholders' equity permits a real **X4 book/TL**
partial factor but `OperatingIncomeLoss` is a *candidate*, not automatically
`Earnings Before Interest And Taxes`; no corroborating separately tagged
FY2025 interest-expense fact or original 10-K EBIT bridge was established.
Using zero interest expense from absent XBRL tags would fabricate evidence.

### Actual Decimal research-only calculations

The `Ohlson_non_FFO_decimal.partial_logit_excluding_FUTL` field is the
*weighted sum of eight source-supported Ohlson terms and intercept*, **without
FUTL**, not the fitted original O logit, Ohlson probability, or S8 score:

| Ticker | Non-FFO logit contribution | Complete Ohlson O | Complete Altman Z | S8 |
|---|---:|---|---|---|
| INOD | −5.343991 | N/A | N/A | **N/A** |
| TMDX | −5.265343 | N/A | N/A | **N/A** |
| CRMD | −5.232351 | N/A | N/A | **N/A** |
| PENG | −4.575250 | N/A | N/A | **N/A** |
| ETON | −1.650108 | N/A | N/A | **N/A** |

`Altman_decimal.weighted_terms` separately reports only facts with
independent verified accounting inputs (e.g. real WC/assets, retained
earnings/assets, and the appropriate book-equity or revenue ratio).
Both functions explicitly return `S8=null` and reject invalid denominators.
The `UNVERIFIED_NI_PLUS_DA_CANDIDATE` field is labelled as a *candidate
arithmetic sum only* and is not a company FFO measure or scored model input.

## Private reproducibility and integration

**Four new files only**:
`app/scoring_v10_s8.py`, `scripts/scoring_v10_s8.py`,
`tests/test_scoring_v10_s8.py`, and `docs/SCORING_V10_S8.md`.

Actual private report: `E:/M10/.scoring_v10_private/s8/research_v10_1.json`;
SHA-256 `6230607d80477725961e91dd9acc1acdecb1eb8bf8e258214a6f7933cda7d9d8`;
sidecar `research_v10_1.json.sha256`. Replayed from the original ZIP +
V9 sealed report + frozen private contract + preserved V6 header receipts.
No SEC/FRED HTTP calls, paid API, bypass, production DB or installed EXE.

From the V10 worktree:

```powershell
python -m unittest discover -s tests -p test_scoring_v10_s8.py -v
python scripts/scoring_v10_s8.py --verify E:/M10/.scoring_v10_private/s8/research_v10_1.json
# For a new receipt choose a fresh filename:
python scripts/scoring_v10_s8.py --out E:/M10/.scoring_v10_private/s8/fresh_receipt.json
```

The API `audit_sources(bulk=..., v9_path=..., frozen_source=...)` returns
five source-backed `stocks[ticker]` dictionaries with raw original filing
facts, original and pinned source hashes, explicit accounting evidence gaps,
partial Decimal Ohlson/Altman calculations, `S8=None`, and
`canonical_accepted=False`. `verify_private_receipt(path, ...)` checks the
sidecar SHA **and** recalculates every issuer from original immutable
sources; a forged report with a replaced valid SHA still fails. The CLI
exclusively creates new reports under the V10 private directory and refuses
to overwrite old receipts. Nine standard-library tests passed including
real five-stock source replay, independent 60-digit Decimal reference,
original SIC variant, false cover-page MVE prevention, null-vs-true-zero,
and forged/resealed tamper rejection.

### Open gates to achieve the first real full S8

1. Establish a historically faithful, explicitly **versioned** original
   Ohlson `funds provided by operations` mapping in an authoritative
   accounting source and independently reconcile that exact definition to
   each original FY2025 filed cash-flow statement. No blanket CFO proxy.
2. Produce independently verified original 2025 EBIT bridges; for INOD
   verify the original 10-K SIC and correct nonmanufacturing application.
3. For TMDX, CRMD, PENG, ETON, produce independent FY-end exchange-local
   historical **price × actual shares** or dated verifiable equity market
   value for the original public-manufacturing X4. Reject cover-date floats.
4. Bind the remaining frozen Altman Z_Q normalization and accounting edge
   cases, plus dated PIT GNP vintage before any canonical promotion.

Until those gates are met: **five S8 N/A, new full scores 0**.
