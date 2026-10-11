# MERİDYEN M10 V9 — CRMD FY2025 original Piotroski S9

**Verified outcome:** CRMD **S9 = 55.55555555555556 / 100**, **5 / 9**
original Piotroski signals, `REAL_SCORE_ACCEPTED_RESEARCH`. Calculated
independently with the original frozen V7 nine-signal contract and a second
60-digit Decimal reference. Historical canonical PIT acceptance remains **zero**.
This is a dated FY2025 financial statement research score, **not** a score as of
FY2025 year-end. The original 2025 10-K was filed **2026-03-05**.

All source data below come from official SEC original 10-K body bytes or the
existing SEC Companyfacts/Submissions cache; no financing or source values were
invented. The local SEC FY2024 10-K body was fetched once with a configured
legitimate SEC contact, HTTP 200, and cached in V9-private storage. It is never
re-fetched during score calculation or acceptance replay.

## Source identity and strict replay

| Official source | SEC accession / period | Original local SHA-256 |
|---|---|---|
| CRMD FY2025 consolidated 10-K, filed 2026-03-05 | `0001213900-26-023889`, 2025-12-31 | `8c0d3d8e015ca200773b6612cb3d3e773cbedd9cc03b2bb7b58b02e56128b500` |
| CRMD FY2024 consolidated 10-K, filed 2025-03-25 | `0001013762-25-001852`, 2024-12-31 | `0e81486909c550385c08553e5c37bf7de2bbff77c5ce3fdb8f6a1a276772a52a` |
| SEC Companyfacts bulk CRMD original JSON | CIK `0001410098` | `b75757faacc84388fbe591a3ec2593969ffefe3c9ea86056a188a6fcb0c2f8bb` |
| SEC Submissions CRMD original JSON | CIK `0001410098` | `3a7214421e9ce0addd9b96cb1e6e554ed92f5e6d6b6d5f669bb6cf4177ca143f` |

Direct official filing links:

- [FY2025 original 10-K](https://www.sec.gov/Archives/edgar/data/1410098/000121390026023889/ea0278169-10k_cormedix.htm)
- [FY2024 original 10-K](https://www.sec.gov/Archives/edgar/data/1410098/000101376225001852/ea0234537-10k_cormedix.htm)

Original S1–S14 plugin contract SHA-256
`53dce841fd5ebdfeb00636f327493be1255ea8b60e6df4eadd921a7098813794`.
The scoring method remains V7: annual current and previous issuer ROAs use
opening assets; leverage uses long-term interest-bearing debt / average assets;
gross margin is `(revenue - total COGS) / revenue`; other six signals and
`100 × total / 9` are unchanged. Prior-year income, sales, current balance
sheet and margins come from FY2025 10-K comparative columns; FY2023 opening
assets from the original FY2024 10-K accession. Reported fact records retain
original accession, filed date, fiscal window and fact digest.

## Exact source-based gross margin correction

FY2025 SEC 10-K **consolidated statements of operations** explicitly show
`Cost of sales (exclusive of amortization of intangibles)` and a distinct
`Amortization of intangibles` line. The latter uses **custom inline XBRL**
`crmd:AmortizationOfIntangibles` with unit USD and `scale=3` in contexts
`c0` (FY2025) and `c9` (FY2024). The basic
`us-gaap:CostOfRevenue` tag **omits** that amortization component.

| Audited 2025 10-K comparative, USD millions | FY2025 | FY2024 |
|---|---:|---:|
| Revenue (all recognized sales and contracts) | 311.709 | 43.472 |
| Tagged `CostOfRevenue` excluding amortization | 22.089 | 3.034 |
| Separate customer/product intangible amortization | **13.872** | **0.156** |
| **Actual total Cost of Goods Sold for V7** | **35.961** | **3.190** |
| Gross profit from audited statement | 275.748 | 40.282 |
| Gross margin (reported) | 88.4633% | 92.6619% |

The previously unexplained **13,872,000** and **156,000** USD differences
are exactly the separately presented intangible amortization, rather than
missing source accounting. Original **FY2024 10-K** independently shows
2024 revenue **43,472,170 USD**, original all-in cost of sales
**3,190,534 USD**, gross profit **40,281,636 USD**, and explicitly states
licence intangible amortization is treated as cost of sales. The 2025
comparative is presented in USD thousands, with the expected reporting
rounding. Both years' 2025 source inline rows were independently checked for
the exact custom tag, scale, contexts and displayed amounts. Correct
`F_DELTA_GROSS_MARGIN = 0` because margin declined.

## FY2025 convertible and FY2024 debt classifications

FY2025 audited balance sheet displays **Convertible senior notes, net of
deferred financing costs: 144,626 thousand USD** and a dash for 2024. The note
reconciles **150,000 thousand USD principal − 5,374 thousand USD discount =
144,626 thousand USD carrying value**, issued on August 12, 2025 and
maturing in 2030.

**Important source taxonomy defect:** The FY2025 **audited balance sheet**
line is marked inline as `us-gaap:DeferredTaxLiabilitiesOther` with
`scale=3` (correct dollar magnitude, semantically incorrect tag). Its note
section repeats 144,626 but marks it
`us-gaap:ConvertibleDebtNoncurrent` with `scale=0` (correct concept,
incorrect dollar magnitude). That note's SEC Companyfacts value is thus
**144,626 USD** instead of the audited **144,626,000 USD**. V9 reconciles the
**original visible balance sheet, the note, original inline scales and the
issuer's acquisition financing timing**, and never promotes the incorrectly
scaled Companyfacts note number.

The original **FY2024 10-K** exhaustively lists current liabilities
33,839,632 USD and a single noncurrent **operating lease** liability
349,091 USD, totaling exactly 34,188,723 USD liabilities. No residual
long-term bank, convertible note or other interest-bearing borrowing exists
within the presented balance sheet. The FY2025 notes were issued after that
fiscal close; prior notes are zero. Operating leases remain separately
classified and are not treated as `LongTermDebt` under V7's mapping. Current
and noncurrent financing leases appearing in 2025 are not summed with the
convertible carrying value in this frozen bond/debt tag implementation;
including them would not reverse the leverage **binary** verdict.
Therefore `F_DELTA_LEVERAGE = 0`: net note indebtedness increased.

No parent and child debt tags were added together; par principal was not
double-counted with the amortized net carrying value. The result is
**Research-only**. Canonical point-in-time publication chronology beyond the
verified SEC filing metadata was not promoted.

## Actual nine frozen binary signals

| Frozen Piotroski signal | Verified value |
|---|---:|
| F_ROA — ROA positive | 1 |
| F_CFO — operating cash flow positive | 1 |
| F_DELTA_ROA — ROA improved | 1 |
| F_ACCRUAL — CFO exceeds net income | 1 |
| F_DELTA_LEVERAGE — long-term leverage declined | 0 |
| F_DELTA_LIQUIDITY — current ratio improved | 0 |
| F_NO_COMMON_EQUITY_ISSUANCE — no new equity | 0 |
| F_DELTA_GROSS_MARGIN — gross margin improved | 0 |
| F_DELTA_ASSET_TURNOVER — turnover improved | 1 |
| **TOTAL** | **5 / 9 = 55.55555555555556** |

Source-verified 2025 common equity proceeds include public offering,
at-the-market and stock option transactions. A positive original SEC
10-K issuance fact is sufficient to assign no-equity-issuance = 0;
mere absence would **not** establish no issuance.

## Implementation, private receipts and commands

Created **only** these four new tracked files:
`app/scoring_v9_crmd.py`,
`scripts/scoring_v9_crmd.py`,
`tests/test_scoring_v9_crmd.py`,
`docs/SCORING_V9_CRMD.md`.

Public integration API:

```python
from app.scoring_v9_crmd import calculate
result = calculate(companyfacts_raw, submissions_raw, body_2025, body_2024)
# result["score_status"] == "REAL_SCORE_ACCEPTED_RESEARCH"
# result["verified_signals"] == 9; result["positive_signal_count"] == 5
# result["score"] == 55.55555555555556
```

The offline CLI reads original V6/V8-private receipts, the existing SEC bulk
ZIP's single CRMD CIK member and the V9-private FY2024 official 10-K cache. It
recalculates from those bytes and verifies the entire newly sealed report
byte-for-byte on every subsequent run.

```powershell
cd E:\M10\.scoring_v9
python -B scripts/scoring_v9_crmd.py
python -B scripts/scoring_v9_crmd.py --verify-only
python -B -m unittest tests.test_scoring_v9_crmd -v
```

Private saved evidence (outside Git):

- `E:/M10/.scoring_v9_private/crmd/report.json`
- `E:/M10/.scoring_v9_private/crmd/report.json.sha256`
- `E:/M10/.scoring_v9_private/crmd/task9_jones_v9_crmd/responses/` — one
  official FY2024 10-K response and its URL/status/SHA receipt

V9-private report digest:
`fcb7c20d8ec7f01e5b554b69a12b4e3a3180860f1bdb5108e472a253bd19693f`.
Existing V1–V8 tracked code, live databases, EXE, previous scores and
other worker-owned files were not modified.
