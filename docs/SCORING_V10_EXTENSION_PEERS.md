# MERİDYEN M10 V10 — Historical S10 window and TMDX/PENG original S11 peers

**2026-10-11 — Completed offline independent source audit; 0 newly accepted full scores.**

The original model source `S1_S2_S14_CANONICAL_SOURCE.md` has SHA-256
`53dce841fd5ebdfeb00636f327493be1255ea8b60e6df4eadd921a7098813794`.
The 17 genuine pre-existing V9 Research scores remain unchanged. The extension
does not touch the frozen source, original S11/S10 engines, old receipt files,
DB, application binaries or production UI.

## 1. S10 original FY2020–FY2024 five-residual window

The original S10 Dechow–Dichev model takes current TCA scaled by average
assets and regresses it against prior, current and following fiscal-year CFO,
plus an intercept, using **a distinct annual original SIC × accounting-regime
industry peer panel**. A full quality score requires five consecutive real
annual target residuals, five comparable peer AQ series, the peer distribution
and an accepted frozen sigma/percentile convention.

The proposed FY2020–FY2024 window **eliminates the need for unavailable
FY2026 CFO** but instead requires exact FY2019 opening balance sheets, FY2025
CFO lead values, and **five dated, independently sourced year-specific panels**.
The code checks all five target companyfacts SHA pins against the original SEC
bulk ZIP and runs the same original-year accession and dollar-unit filters as
`app/scoring_v10_s10.py`; all design rows are checked a second time with
**65-digit Decimal** arithmetic.

| Target | Exact FY2020–FY2024 design rows independently verified | Full S10 |
|---|---|---|
| INOD | none | **N/A** |
| TMDX | none | **N/A** |
| CRMD | **FY2022, FY2023** | **N/A** |
| PENG | none | **N/A** |
| ETON | none | **N/A** |

CRMD FY2022 **TCA = USD 2,285,613**, average assets **USD 65,491,917.50**,
scaled TCA **0.03489916141178795**. Original fiscal accessions: FY2021
`0001213900-22-015852`, FY2022 `0001213900-23-024310`, FY2023
`0001213900-24-021585`.

CRMD FY2023 **TCA = USD 14,315,240**, average assets **USD 72,049,108**,
scaled TCA **0.19868726202689421**. Original fiscal accessions: FY2022
`0001213900-23-024310`, FY2023 `0001213900-24-021585`, FY2024
`0001013762-25-001852`. Their official 2022/2023 10-K body SHA pins are
`fe732c01dfb628975779efdb1cfab07faa52f80e9e2a86b2422184870b02ed84`
and `e4996595c8bec4deec5e1e504dc4cb19035cc218ebc7e97bb8f383c4b361e807`.
The original statements explicitly prove the relevant FY2021–23
short-term-borrowing zero classification. The extension independently
recomputes TCA and normalization from exact accession-pinned SEC dollar
facts; **no real target residual or S10 score** is inferred from these rows.

The existing bounded historical 10-K SGML cache inventory across the private
Task9/legacy V6/S10 **source directories actually inspected** yielded **zero
verified FY2020–2024 SGML headers** for each of those five fiscal years.
That is a limitation of the *available cached evidence*, not a claim that no
older SEC filings exist. The SEC bulk ZIP is a financial-facts source and
does not itself authenticate annual SIC or accounting-regime cohorts.
Collecting 20+ complete, historical original SEC headers, financial
classifications and original-year cash-flow boundaries across five separate
panels is a major new data-acquisition task, and has not been attempted here.
The frozen contract also leaves the sample/population sigma choice and
percentile tie algorithm unspecified; neither can be invented to enable a score.

**S10 complete FY2020–FY2024 results: 0.** No S11 FY2025 peer cache was
silently recycled into S10. No historical PIT evidence claimed.

## 2. Independent source-byte re-performance of TMDX and PENG S11

Existing legacy V6 original source reports were located in
`E:/M10/.scoring_v6_private/jones_tmdx` and `.../jones_peng` and checked
against their adjacent SHA-256 seals. The unchanged `scan_task9` and
`compute_s11` engines were replayed with **`SECCache(contact=None,
request_budget=0)`**, reading original SEC Companyfacts and original SGML
10-K header bytes from existing caches. Financial records, exact historical
SIC, original 10-K accession, CIK uniqueness, year window and independently
selected eight-input source material were compared with the old reports.
All SEC HTTP requests were disabled and **zero** occurred.

| Target | FY2025 original 10-K | Dated SIC | 8/8 precheck peers | Fully eligible independent peers | Frozen minimum | S11 |
|---|---|---|---:|---:|---:|---|
| TMDX | `0001193125-26-067032` | **3845** | 13 | **12** | 20 | **N/A** |
| PENG | `0001616533-25-000061` | **3674** | 2 | **1** | 20 | **N/A** |

Original SGML SEC header SHA-256:

- TMDX: `04ab2e9d8b53891d57d629585a5e94aa6a6c1b63f301280733f339af59ee8c2c`
- PENG: `462a4a7d6accfa1009a80ca68c29a783abfba77337420648ce0ddf33861a631d`

Original SEC Companyfacts bulk member SHA-256:

- TMDX: `8096066125323b72557bd9d582cfab4bcdec59b814cee4e082ede5ade1a800ab`
- PENG: `7f49ae1db8700690e6ea142ddafad7a524e5ab04b5a49e16e5be72bd82ebaca6`

Legacy source report SHA-256 (verified against original private seals):

- TMDX: `9db42edfbac5940681c08fa5a8aadfc2c13cc68d452e8712e548f95e5d7058a5`
- PENG: `eb03b2a16366fb6836def74f725022af7136280acd9a68f1d06f8da301451c76`

Both issuers' exact eight original target SEC financial inputs are accepted
as a research source inventory. No real ≥20-issuer industry regression can
be fitted from 12 or 1 eligible observations. In particular there are **no
approved OLS betas, NDA, DA or S11 scores**. Fiscal-year PENG is anchored to
**August 29, 2025**; December 31 peer periods are not assumed comparable.
The 2025 SIC7374 INOD cohort remains a different industry.

## 3. Reproduction and scope

New **only** tracked files:

```text
app/scoring_v10_extension_peers.py
scripts/scoring_v10_extension_peers.py
tests/test_scoring_v10_extension_peers.py
docs/SCORING_V10_EXTENSION_PEERS.md
```

Private auditable result (contains original-source digests and eligible peer
identities, **not raw SEC filing bodies**):

```text
E:/M10/.scoring_v10_private/extension_peers/source_replay.json
E:/M10/.scoring_v10_private/extension_peers/source_replay.json.sha256
```

Receipt SHA-256:
`ebfb0c47d6407b98f35dc41fa8997a2e465da33418b4c597585fb194e73e6066`.

```powershell
cd E:\M10\.scoring_v10
E:/M10/.venv/Scripts/python.exe -B scripts/scoring_v10_extension_peers.py --verify-only
E:/M10/.venv/Scripts/python.exe -B -m unittest tests.test_scoring_v10_extension_peers -v
```

The `--verify-only` path **recomputes all source-driven results** before
comparing the current private JSON bytes and adjacent SHA; resealing a forged
result cannot bypass this check. Windows original-cache integration tests
must **SKIP on CI machines without private SEC inputs**. All existing research
score conclusions are preserved: V10 total **17 full prior Research scores,
zero additional S10/S11**; no extra historical S16-C/PIT observations.
