# M10 scoring completion V10 — INOD original S8 FFO / EBIT extension

2026-10-11 JST. Isolated Windows worktree `E:/M10/.scoring_v10`,
branch `codex/scoring-completion-v10`, starting commit `d2ca27b`.
**Research extension outcome: one additional strongly reconciled Altman
candidate, zero newly accepted original full S8 scores. INOD S8 remains N/A.**
There is no change to the frozen formulas, old S8 pipeline, original 17 scores,
live database or production executable.

## Original sources and provenance

- Original 2025 [Innodata SEC Form 10-K](https://www.sec.gov/Archives/edgar/data/903651/000110465926020655/inod-20251231x10k.htm),
  filing accession **0001104659-26-020655**, year ended **2025-12-31**,
  filed **2026-02-26**. Statements F-4 (balance sheet), F-5
  (income), F-6 (equity), F-7 (cash flow) and the segment-revenue/operating-
  profit note independently cross-check the FY2025 numerators.
- Original [SEC 10-K filing index](https://www.sec.gov/Archives/edgar/data/903651/000110465926020655/0001104659-26-020655-index.htm):
  **SIC 7374**, CIK **0000903651**, 10-K filed **2026-02-26**,
  accepted **17:22:13**, FY-end **2025-12-31**. This is a stronger direct
  historical SIC verification than the V10 prior research mapping. The live
  SEC index was read online but its original HTML has **not** been archived
  with a byte SHA: `OFFICIAL_SEC_INDEX_LIVE_VISIBLE_NOT_OFFLINE_SHA_REPLAY`.
- Original v0.28.1 `S1_S2_S14_CANONICAL_SOURCE.md`,
  **SHA-256 `53dce841fd5ebdfeb00636f327493be1255ea8b60e6df4eadd921a7098813794`**,
  lines 1325–1442, verified using the existing offline V10 SHA gate.
  It fixes nonmanufacturing `Z'' = 6.56 X1 + 3.26 X2 + 6.72 X3 + 1.05 X4`
  (book equity allowed, **no additive 3.25**) and
  `S8 = WA(Z_Q, O_Q)` at 50/50. Original Ohlson
  `FUTL = FundsFromOperations / TotalLiabilities` has no supplied
  accounting reconstruction.
- The original SEC Companyfacts issuer ZIP member, exact original 10-K
  accession facts, V9 original frozen receipt and existing V10 receipt are
  reverified via `app.scoring_v10_s8.verify_private_receipt`. INOD original
  Companyfacts member SHA:
  `6ccc9dcc93b9c303cee51c166f345350fb16258408c884e2ed5d1231f2741b38`.
  This proves the filed numeric XBRL records, while the new income statement
  crosswalk above is an *auditor-reviewed excerpt transcription*, rather
  than a byte-pinned copy of the original SEC HTML. The extension explicitly
  retains `source_original_HTML_sha256 = null`.

## Verified FY2025 original 10-K statement bridge

All amounts below are USD, filed in thousands and shown here in millions:

| FY2025 original SEC line | Million USD | Independent relationship |
|---|---:|---|
| Total assets | 168.593 | Assets = liabilities + consolidated equity |
| Total liabilities | 61.531 | SEC exact original 2025 10-K XBRL |
| Current assets / current liabilities | 135.394 / 50.532 | WC = 84.862 |
| Retained earnings FY2024 / FY2025 | 18.977 / **51.158** | 18.977 + net income 32.181 = **51.158** |
| Parent company equity | 107.145 | Original balance sheet `StockholdersEquity` |
| Noncontrolling interest | **−0.083** | Unusual negative NCI, explicitly present in SEC balance sheet |
| **Total consolidated equity** | **107.062** | 107.145 − 0.083 = 168.593 − 61.531 |
| Revenue | 251.663 | F-5 filed income statement |
| Direct operating / selling-administrative costs | 152.184 / 59.606 | F-5 and segment disclosures |
| **Operating profit** | **39.873** | 251.663 − 152.184 − 59.606; separately segment summed |
| Net interest **income** | 1.552 | Operating profit + 1.552 = pretax income 41.425 |
| Pretax income / income taxes | 41.425 / 9.244 | Net income = 32.181 |
| Combined depreciation / amortization | 6.889 | F-7 filed adjustment, FY2025 |
| Other noncash adjustments | 16.696 | Stock compensation 11.144 + deferred taxes 4.101 + credit loss 0.108 + pension 1.343 |
| Net income + all noncash adjustments | **55.766** | Cash before changes in working capital, not validated original FFO |
| Changes in working capital | −9.014 | FY2025 F-7 cashflow rows summed |
| GAAP operating cash flow | **46.752** | 55.766 − 9.014, independently matches F-7 |
| **Cash paid** for interest | 0.229 | Cash-basis F-7 disclosure; NOT gross accrual interest expense |

**EBIT evidence outcome:** SEC FY2025 original F-5 and the segment note prove
`operating profit = 39,873,000` and a complete bridge to `pretax income`.
This is earnings from operations before reported *net* interest income and
tax, but the filing excerpt does not separately identify **total gross
accrued interest expense**. Specifically, the Agility segment separately
reports `1,000` interest expense and DDS separately reports `−1,553,000`
interest expense/income *net*; these cannot establish how gross expense and
income netted across the group. FY2025 cash interest paid `229,000` is
not a valid proxy for accrual interest expense. Therefore the frozen
`EBIT` acceptance field stays **null**; the exact source-reconciled
`operating_profit` is exposed as a **conditional** EBIT scenario.

**Equity classification outcome:** Parent-attributable `StockholdersEquity`
is **107.145m**, whereas total consolidated book equity balancing A−L is
**107.062m**. The 83,000 USD NCI difference is real. The frozen
nonmanufacturer X4 permits `book equity` but does not distinguish
parent-only from consolidated equity in the unusual negative-NCI case.
Both scenario results are reported; neither is silently promoted.

## Independent Decimal Altman scenario (not accepted Z)

Using **only** the conditional assumption `EBIT := issuer operating profit`
and the original frozen Z'' (without an intercept):

| Weighted term | 60-digit Decimal result (rounded) |
|---|---:|
| 6.56 × (135.394 − 50.532) / 168.593 | 3.302003760536 |
| 3.26 × 51.158 / 168.593 | 0.989217108658 |
| 6.72 × **39.873** / 168.593 | 1.589310113706 |
| 1.05 × **107.062** / 61.531 | 1.826966894736 |
| **Conditional Z'' using total consolidated equity** | **7.707497877636** |
| **Conditional Z'' using parent equity** | **7.708914236869** |

The exactly replayed 60-digit consolidated variant:
`7.70749787763563263116337878477596777645963693612937197380148`.
All coefficients and denominators are recomputed independently in the tests.
**Accepted Altman Z = null; accepted Z_Q = null.** The frozen legacy
safety fallback uses knots `1.8, 2.7, 3.0, 3.5` derived from the ordinary
Z scale; binding that unmodified fallback to nonmanufacturer Z'' requires
independent variant-specific calibration evidence.

## Ohlson FFO decision: N/A, historical equivalence not proved

Original [Ohlson (1980)](https://doi.org/10.2307/2490395) reports
`funds provided by operations`, while the frozen Meridyen
`FundsFromOperations` lacks an explicit 2025 US-GAAP mapping.
An independently checked German National Library
[dissertation, p.44 footnote 18](https://d-nb.info/1191365735/34)
states that funds provided by operations are no longer reported and the
authors use pretax income + depreciation and amortization as an
**approximation**. A separate
[UCR research data appendix](https://faculty.ucr.edu/~abarinov/Data%20Appendix%20Distress.pdf)
likewise operationalizes a `PI + DP` approximation. An independent
[TradingView FFO definition](https://www.tradingview.com/support/solutions/43000563886/)
adds other noncash items and deferred taxes. These modern conventions
**are not proofs that original Ohlson 1980 FFO equals any one of them**.

| Independently evidenced FY2025 number | Million USD | FFO acceptance |
|---|---:|---|
| Net income + D&A | 39.070 | Candidate only |
| Pretax income + D&A (Compustat PI+DP approximation) | 48.314 | Candidate only |
| Net income + all noncash adjustments before WC | 55.766 | Candidate only |
| Modern US-GAAP CFO after WC | 46.752 | Candidate only |
| **Original Ohlson funds from operations** | **N/A** | **No authoritative identical measurement** |

The four different candidates give four different FUTL ratios against
`61.531m` liabilities. None may be substituted into the frozen Ohlson
equation; **accepted FFO, FUTL, Ohlson O, O_Q and S8 stay null**.
The pre-existing independently audited Ohlson *non-FFO* contribution
`−5.343991` is partial arithmetic only and must not be displayed as
O-score. Modern revised BEA/FRED GNP deflator readings are not an
original historical 2025 PIT vintage.

## Files, offline replay and audit

Only four new tracked files are introduced:
`app/scoring_v10_extension_s8.py`,
`scripts/scoring_v10_extension_s8.py`,
`tests/test_scoring_v10_extension_s8.py` and this note. The app uses
standard-library `Decimal` at 60-digit precision, checks three
different original SEC statement bridges, rejects even one-thousand-dollar
tampering, verifies original SEC Companyfacts record SHA/accession via the
pre-existing V10 verifier, and explicitly returns **zero full S8 scores**.
No network calls, paid API, SEC rate-limit retry, DB writes, installations,
EXE rebuild, merge or PR actions.

Private receipts, both SHA sealed and immutable:

- v1 (before the official online index SIC was found):
  `E:/M10/.scoring_v10_private/extension_s8/inod_fy2025_v10_extension_v1.json`
  SHA `ff142453840c3b465eccaf6ab4e7755db771a7c201ca42ac90e346497bcb18b0`.
  Historical replay compatibility preserves exactly the prior evidence state.
- **v2**, with original FY2025 SEC filing-index SIC evidence:
  `E:/M10/.scoring_v10_private/extension_s8/inod_fy2025_v10_extension_v2.json`
  SHA `0327998aad23a77f0a7585e3d80b020a884a3e24a13076d0466f2b60375b7428`.

Run from `E:/M10/.scoring_v10`:

```powershell
python -m unittest discover -s tests -p test_scoring_v10_extension_s8.py -v
python scripts/scoring_v10_extension_s8.py --verify E:/M10/.scoring_v10_private/extension_s8/inod_fy2025_v10_extension_v1.json
python scripts/scoring_v10_extension_s8.py --verify E:/M10/.scoring_v10_private/extension_s8/inod_fy2025_v10_extension_v2.json
```

**6/6 focused tests passed** (real offline original five-issuer V10 replay
and INOD cross-check, independent Decimal Altman, divergent Ohlson FFO
definitions, negative-NCI classification, source arithmetic tamper gate
and preserved v1 receipt replay). Remaining original S8 acceptance gates:
versioned authoritative original Ohlson FFO mapping and issuer-specific
2025 reconciliation; frozen EBIT identity after gross-interest disaggregation;
explicit nonmanufacturer book-equity policy and Z_Q calibration; and
date-correct GNP-vintage evidence if historical PIT acceptance is requested.
