# MERİDYEN M10 V9 — Frozen S8 Ohlson and S10 Dechow–Dichev implementation

**11 October 2026 (JST)** · isolated `E:/M10/.scoring_v9` · base commit `727635e`.
The present effort reuses **five original V8 SEC Companyfacts SHA-pinned sources**,
performs source-backed **real numeric S8 subcomponent calculations**, and
implements the authentic S10 annual regression as a reusable deterministic
engine. The final SHA-256 sealed private receipt is
`E:/M10/.scoring_v9_private/s8_s10/v9_evidence_v2.json`,
hash `80ae714f2dd85e2b3f927071876e00a4de0ef851497481e37e930d972319a746`.
Research scope only: **S8 0 complete, S10 0 complete, canonical 0**.
V8's previously accepted scores/receipts and all existing files remain unchanged.

## 1. Original frozen source recovered and checked

The owner-installed private plugin provides the full
`S1_S2_S14_CANONICAL_SOURCE.md` in the Meridyen Equity Research 0.28.1
local plugin cache. We verified SHA-256
`53dce841fd5ebdfeb00636f327493be1255ea8b60e6df4eadd921a7098813794`.
The source is **read locally only**, not checked into Git.

| Model | Source section (1-indexed line region) | Actual frozen rule |
|---|---|---|
| S8 | ~1325–1442 | Public manufacturing Altman Z or justified nonmanufacturing Z''; Ohlson 9-factor logit; **S8=WA(Z_Q,O_Q), default 50/50** |
| S10 | ~1486–1544 | Dechow–Dichev working-capital accrual regression; year × industry × accounting-regime cohorts; five years' residual sigma; score = 100×(1−peer percentile) |

S8 exact Ohlson linear predictor:

`O = −1.32 −0.407 SIZE +6.03 TLTA −1.43 WCTA +0.0757 CLCA −1.72 OENEG −2.37 NITA −1.83 FUTL +0.285 INTWO −0.521 CHIN`.

`FUTL = FundsFromOperations/TotalLiabilities`;
`O_Q = 100×(1−logistic(O))`. The frozen source **does not specify
an exact contemporary SEC GAAP tag or derivation for FundsFromOperations**.
It must be established in an accession-specific issuer cash-flow statement.
Modern CFO can be a useful candidate but is **not silently substituted**
for the original FFO. This blocks each full Ohlson score even though
the other source-supported numerical terms are available. Altman issuer
variant, retained earnings, EBIT, market value equity and sales must also
be demonstrated before a full S8 model can be independently accepted.
CHIN both-income-zero is a distinct unresolved denominator edge case;
zero FFO with genuine documentation remains distinguishable from missing.

## 2. GNP original 1968 base and actual BEA/FRED observations

Original Ohlson (1980) **SIZE** is
`ln(assets in USD / GNP price level)`. The price-level index must use
**1968 = 100**, and Ohlson uses the **calendar year before the balance
sheet year**. The private frozen plugin states the Ohlson coefficient
but does not reproduce this deflator normalization; the convention is
grounded in Ohlson's [1980 primary paper](https://doi.org/10.2307/2490395)
and explanatory paper citations.

Official BEA/FRED **annual GNP implicit price deflator**
`A001RD3A086NBEA`: [data table](https://fred.stlouisfed.org/data/A001RD3A086NBEA),
[revision history](https://alfred.stlouisfed.org/series?seid=A001RD3A086NBEA).
The series currently uses **2017=100**; these values were cross-checked
against the official table updated **2026-09-30**:

| Calendar year | Official revised 2017=100 | Role |
|---|---:|---|
| 1968 | 18.246 | Rebase denominator |
| 2023 | 122.361 | For FY2024 balance-sheet year |
| 2024 | 125.496 | For FY2025 balance-sheet year |

`GNP_1968_100(year) = 100 × GNP_2017_100(year) / 18.246`.
The fiscal year end is issuer specific (PENG ends in August), but the
**preceding calendar year** is deliberately selected from each
balance sheet year. Current revised values are **not original as-of-2024
or as-of-2025 release vintages**. ALFRED documents revisions; vintage-specific
archived observations were not retrieved/verified. Local Python's attempted
direct FRED CSV download timed out. Values are explicit official web-table
transcriptions with series and observation date, **not SHA-pinned raw FRED
bytes**. Thus every SIZE is labeled *2026-revised Research diagnostic*
and historical PIT stays false.

### Actual original-source S8 SIZE computations

All S8 annual inputs used the five immutable SEC ZIP member hashes from
`app/scoring_v8_s8_s10.py`, and each selected source row has its
own original-filing accession, fiscal date and record SHA. The source
inventory's original-year `10-K` filter was reused. Complete non-FFO
Ohlson arithmetic can be found under `S8.years[year].ohlson` in the
private report.

| Stock | SIZE FY2024 | SIZE FY2025 | Original FFO complete | S8 score |
|---|---:|---:|---|---|
| INOD | 12.0386639548 | 12.4094998907 | No | N/A |
| TMDX | 13.9970043501 | 14.2559045738 | No | N/A |
| CRMD | 12.0851363440 | 13.9987790359 | No | N/A |
| PENG | 14.6033888555 | 14.6704639021 | No | N/A |
| ETON | 11.6396610112 | 11.8050393047 | No | N/A |

These are natural logs of dollar assets divided by the re-based GNP
index, **not 0–100 scores or bankruptcy probabilities**. No S8 score
was produced for any of the ten company/year combinations.

## 3. S10: original regression and implementable acceptance

The plugin's actual frozen definition is:

`TCA_t = ΔCA_t − ΔCash_t − ΔCL_t + ΔSTDebt_t`.

`TCA_t/A_t = α + β₁ CFO_(t−1)/A_t + β₂ CFO_t/A_t + β₃ CFO_(t+1)/A_t + ε_t`.

`A_t` is **preferably average assets**. Industry × accounting-regime
regression is fitted separately **for every fiscal year**. The target's
five consecutive fitted residuals yield
`DD_AQ = σ(ε[t−4]..ε[t])`, and S10 then uses a comparable DD_AQ
peer percentile; **minimum 20 independent peers and five residual
years are preferred** in the frozen contract. It allows low-confidence
diagnostics with fewer observations, but no reduced-panel result is
presented as full independently accepted S10 here.

V9 implements the original TCA arithmetic, average-asset regression
design, four-coefficient least squares with singularity detection,
unique SIC/regime/year peer eligibility and source-evidence checks,
plus five-year population/sample sigma diagnostics. Because the
source does not freeze the population-vs-sample sigma or tied percentile
algorithm, it reports those separately and **does not invent an
official normalized S10 score**.

The existing V8 individual fact inventory had 35/35 seven-tag windows for
INOD, TMDX, PENG, ETON, and **32/35** for CRMD (2021–23 original
`AccountsReceivableNetCurrent` absent). These are only raw inventory
facts. V9 found **no dated five-year S10-specific SIC × accounting regime
panels** with ≥20 independent issuers per year. S11's successfully
verified Jones 2025 cohorts are a *different regression*, and cannot
be used as S10 peer evidence. FY2025 S10 residual fitting also calls
for CFO FY2026, which is not an audited full year as of October 2026.
An FY2020–FY2024 five-residual research sequence would require additional
pre-2021 source periods and five separate eligible panels. No such
five-year cohort is evidenced in these pinned inputs.

## 4. CRMD FY2021–23 targeted cached receivables inspection

The exact, pinned CRMD Companyfacts member is
`CIK0001410098.json`, SHA-256
`b75757faacc84388fbe591a3ec2593969ffefe3c9ea86056a188a6fcb0c2f8bb`.
Direct selective examination of four receivable concept families found:

| Fiscal year | Original 10-K evidence | Amount | Defensible use |
|---|---|---:|---|
| 2021 | `AccountsReceivableNet`, accession `0001213900-22-015852`, filed 2022-03-29 | **$45,368** | Genuine reported receivables, alternate tag; classification equivalence to `AccountsReceivableNetCurrent` requires source review |
| 2021 | `IncreaseDecreaseInReceivables`, same accession | $44,080 | Cash-flow change, **not** period-end receivables |
| 2022 | `IncreaseDecreaseInReceivables`, accession `0001213900-23-024310`, filed 2023-03-30 | −$42,143 | Cash-flow movement only; ending balance N/A |
| 2022–2023 | `AccountsReceivableNetCurrent`, `AccountsReceivableNet`, `OtherReceivablesNetCurrent` in exact original annual windows | **N/A** | Do not infer zero |

These are reported **USD** amounts (no automatic thousands multiplier).
The V9 report stores the individual exact SEC fact hashes and accessions.
It does not claim an absent tag means no receivables. The 2021 alternate
tag is a newly identified **real source fact**, not a completed three-year
S10 receivable series. The model's original TCA depends on **current
assets and liabilities, cash and short-term debt**, and CFO lead/lag;
receivables inventory by itself neither completes nor replaces TCA.

## 5. Engineering, evidence and limits

Only four new tracked files were created:
`app/scoring_v9_s8_s10.py`, `scripts/scoring_v9_s8_s10.py`,
`tests/test_scoring_v9_s8_s10.py`, this document. The original
source remains in the user's local plugin installation; the five
underlying SEC files remain in the original bulk ZIP; output only
resides in `E:/M10/.scoring_v9_private/s8_s10`.

Run without installing packages:

```powershell
python -m unittest discover -s tests -p test_scoring_v9_s8_s10.py -v
python scripts/scoring_v9_s8_s10.py --out E:/M10/.scoring_v9_private/s8_s10/v9_evidence_new.json
```

The CLI opens only a **new private JSON** and fails if it already exists.
It also creates a `.sha256` sidecar for byte-level replay validation.
It verifies the original frozen contract SHA and all five prior SEC
Companyfacts pins before calculation. It makes **zero network requests**,
does not write any database, and does not modify other worktrees.
Twelve focused stdlib `unittest` cases pass, including the actual
source hash, original SIZE rebase, CHIN zero-denominator, legitimate zero
FFO versus missing, correct TCA arithmetic, independent 20-peer
OLS coefficients, singular-panel rejection, five-year history gate,
and SHA-pinned CRMD FY2021 source replay.
Regression test input rows are explicitly **synthetic**, used only
to validate numerical code; all actual issuer values come from pinned
private SEC records.
