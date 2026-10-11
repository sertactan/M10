# MERİDYEN M10 — Scoring Completion V10 / Original S10 Dechow–Dichev

**RESULT — no verified full S10 scores.** The new V10 implementation produces
real SEC-sourced annual accounting design rows and an independent four-
coefficient regression, but **does not manufacture** the missing five
historical original SIC × accounting-regime peer cohorts, future FY2026 cash
flow, peer five-year accrual-quality distribution or an unspecified percentile
convention. All five issuers remain **S10 DATA_MISSING**. Existing V9
**17 accepted Research scores** are untouched; no new historical canonical
PIT acceptance.

## Frozen original formula, recovered and hash verified

The original installed private Meridyen Equity Research source
`S1_S2_S14_CANONICAL_SOURCE.md`, SHA-256
`53dce841fd5ebdfeb00636f327493be1255ea8b60e6df4eadd921a7098813794`,
lines **1486–1546**, defines:

```text
TCA_t = ΔCurrentAssets_t − ΔCash_t − ΔCurrentLiabilities_t + ΔShortTermDebt_t
TCA_t / AverageAssets_t
      = alpha + beta1×CFO_(t−1)/AverageAssets_t
              + beta2×CFO_t/AverageAssets_t
              + beta3×CFO_(t+1)/AverageAssets_t + residual_t
DD_AQ = sigma(residual_(t−4) ... residual_t)
S10 = 100 × (1 − peer_percentile(DD_AQ))
```

Annual regressions require a separate, dated **industry × accounting
regime × fiscal year** peer panel. The source *prefers* at least 20 firms and
at least five consecutive residual years, but does not specify sample versus
population standard deviation, the percentile tie algorithm, or how to prove
historical accounting regimes automatically. Consequently the V10 engine
explicitly refuses to identify any numerical diagnostic normalization with
the frozen official S10 score.

**Critical calendar boundary:** to fit an FY2025 residual one must know
**audited FY2026 operating cash flow** for the issuer **and for every
qualified peer**, still impossible as of October 11, 2026. An alternative
FY2020–FY2024 five-residual window would instead need original FY2019
opening balance rows, FY2025 next-year CFO, five true annual peer cohorts
and five-year comparable peer DD_AQ observations. Do not substitute a
2025-only **S11 Modified Jones** SIC7374 roster for the genuine S10 panel.

## Genuine newly recovered CRMD FY2022 and FY2023 evidence

The two SEC FY10-K original bodies were legally downloaded **once each**,
no retry or paid API, using a valid SEC identification:

| FY | Original filing | First SEC filing date | Original cached SHA-256 |
|---|---|---|---|
| 2022 | [Original 10-K](https://www.sec.gov/Archives/edgar/data/1410098/000121390023024310/f10k2022_cormedixinc.htm), accession `0001213900-23-024310` | 2023-03-30 | `fe732c01dfb628975779efdb1cfab07faa52f80e9e2a86b2422184870b02ed84` |
| 2023 | [Original 10-K](https://www.sec.gov/Archives/edgar/data/1410098/000121390024021585/ea0201177-10k_cormedix.htm), accession `0001213900-24-021585` | 2024-03-12 | `e4996595c8bec4deec5e1e504dc4cb19035cc218ebc7e97bb8f383c4b361e807` |

FY2022 audited balance sheet explicitly shows **Trade receivables, net
`-` for 2022 and USD 45,368 for the 2021 comparative**. The 2022 amount is
a defensible **filing-explicit zero**, *not* an absent-tag zero, and 2021's
USD 45,368 corroborates the V9 `AccountsReceivableNet` original
SEC fact. FY2023 original audited balance sheet **does not list an explicit
trade receivables amount**. Its six disclosed current-assets components
sum to the stated total USD **79,450,400**, but an absent receivable line
must **not** become a fabricated GAAP fact or verified numeric zero.
`FY2023 receivables_USD=null` is deliberate. CFO change in receivables
is not an ending balance.

The two original consolidated balance sheets also reconcile exact
FY2021, FY2022 and FY2023 short-term **interest-bearing borrowing = 0**
with the disclosed current liability rows. This zero is backed by audited
full statement enumeration, **not by empty XBRL debt tags**; operating
lease liabilities are tracked distinctly.

The full frozen TCA input vector (`Assets`, `AssetsCurrent`, `CashAndCashEquivalentsAtCarryingValue`,
`LiabilitiesCurrent`, three annual `NetCashProvidedByUsedInOperatingActivities`,
and source-proven short-term borrowings) produced **real diagnostic
normalized regression design rows**:

| CRMD year | TCA, actual USD | Result |
|---|---:|---|
| FY2022 | **2,285,613** | Complete real target design, peer/SIC regression still missing |
| FY2023 | **14,315,240** | Complete real target design, peer/SIC regression still missing |
| FY2025 | N/A | FY2026 original 10-K / CFO does not exist |

Both years are source-backed target **design rows**, **NOT residuals**
or S10 scores: until 20 appropriately dated **independent** peer issuers
and exact annual SIC classification / audited accounting regimes are proven,
there can be no 4-beta peer fit. Other companies' isolated tagged short-term
debt amounts are not assumed exhaustive of all debt classes.

## Engineering deliverables (exclusive worker-owned NEW files)

- `app/scoring_v10_s10.py`: real pinned SEC annual-accession/period
  inventory; exact full-year USD XBRL source facts; fiscal anchors including
  non-December PENG; original CRMD zero/absent statement probes; audited
  borrowing proof; authentic cash-flow lead/lag and DD design;
  strict SEC-original SGML annual SIC; independent **65-digit Decimal
  four-beta full-rank OLS**; separate legacy V9 float-reference
  crosscheck *only for actual eligible cohorts*; verified-peer source
  re-performance; five-year and percentile fail-closed gate.
- `scripts/scoring_v10_s10.py`: reads only original cached SEC Companyfacts
  ZIP, FY2022/2023 official SEC bodies and frozen contract; re-performs all
  calculations offline, and creates/verifies a PRIVATE SHA-sealed receipt.
- `tests/test_scoring_v10_s10.py`: standard-library verification, real
  source amounts and SHA modification rejection, accession checks, genuine
  TCA values, no arbitrary fabricated peers, FY2026 boundary, forged
  resealed receipt rejection. Public Linux CI skips locally private SEC
  caches; the no-source cohort gates still run.
- `docs/SCORING_V10_S10.md`: methodology, reproducible results, exact blockers
  and conservative data classification.

Private response cache and report (none committed):

```text
E:/M10/.scoring_v10_private/s10/task9_jones_v10_s10/responses/
E:/M10/.scoring_v10_private/s10/report.json
E:/M10/.scoring_v10_private/s10/report.json.sha256
```

## Windows validation

```powershell
cd E:\M10\.scoring_v10
python -B scripts/scoring_v10_s10.py
python -B scripts/scoring_v10_s10.py --verify-only
python -B -m unittest tests.test_scoring_v10_s10 -v
```

Private initial report SHA-256:
`94fa154f1cfe12f5ac8930b0cf19950780a61a94bf0c17b1ad312f8f5a4098ec`.
Subsequent private receipts are matched to the *fresh recomputation*,
not merely accepted because their adjacent SHA can be rewritten. The
original five V7/V8 issuer Companyfacts member SHA pins are checked on
every replay. Calculations access only five members from the bulk ZIP,
not the full universe, and make zero network calls.

**Actual remaining gates** before any S10 score: exact per-year industry SIC
and audited accounting regime proof for each peer; ≥20 fully evidenced
independent peers for each of five successive regressions; comparable
FY(t−1)/FYt/FY(t+1) original annual accessions and asset/cash/current-liability/
verified short-term-borrowing components for every firm; target and peer
five-year residual sigma; comparable cross-sectional peer AQ distribution;
frozen percentile/tie and sigma choices. FY2025 endpoint is out of range
until original FY2026 filings are available. No company score is promoted.
