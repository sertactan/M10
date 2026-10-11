# MERİDYEN M10 V8 — S8 Ohlson SIZE / S10 historical peer audit

**Audit date:** 2026-10-11 (JST). **Base:** V7 commit `7af654a05b2c7c6ce466f4248403f48323b306c7`.

**Result:** `S8=DATA_MISSING`, `S10=DATA_MISSING` for **INOD, TMDX,
CRMD, PENG, ETON**. There are **0 new complete Research scores** and **0
new canonical PIT observations**. V7's **15 previously accepted Research
scores** are unchanged. This audit does not change frozen formulas or consume
any service/network/API credits.

## Source and acceptance boundary

- Existing offline SEC bulk: `%LOCALAPPDATA%/S153ResearchTerminal/runtime/bulk/sec/companyfacts.zip`
  (1,410,169,309 bytes at the time of audit). The tool reads **five explicitly
  addressed ZIP members only**, checks their exact JSON SHA-256 hashes against
  previously verified V4/V6/V7 values, and never extracts or scans all 20,440
  members. No HTTP calls, no paid API, and no local DB write.
- Frozen S1–S14 plugin contract SHA-256:
  `53dce841fd5ebdfeb00636f327493be1255ea8b60e6df4eadd921a7098813794`
  (see `docs/RECOVERED_QUALITY_CONTRACTS.md`). The original entire external
  S8 and S10 subsection is **not reproduced in the Git checkout**. Consequently
  the audit does not assert that generic GAAP concept coverage proves any
  derived model variable, scoring threshold, historical peer minimum, or
  normalisation.
- The FY2025 SEC Companyfacts entries are tied to the **exact previously
  established 10-K accessions**. Older-year diagnostics require an original
  FY `10-K`, an exact reported fiscal year-end, valid USD unit and duration
  (330–400 days for flows), and reject distinct conflicting facts. This audit
  does not independently re-verify the older filings' SEC SGML headers or first
  public dissemination timestamps. Thus the diagnostic statuses
  `EXACT_REPORTED_10K_FACT` and hash match are **not** a PIT acceptance.

| Issuer | CIK | FY2025 end | Pinned 10-K accession | Local Companyfacts SHA-256 |
|---|---|---|---|---|
| INOD | 0000903651 | 2025-12-31 | 0001104659-26-020655 | `6ccc9dcc93b9c303cee51c166f345350fb16258408c884e2ed5d1231f2741b38` |
| TMDX | 0001756262 | 2025-12-31 | 0001193125-26-067032 | `8096066125323b72557bd9d582cfab4bcdec59b814cee4e082ede5ade1a800ab` |
| CRMD | 0001410098 | 2025-12-31 | 0001213900-26-023889 | `b75757faacc84388fbe591a3ec2593969ffefe3c9ea86056a188a6fcb0c2f8bb` |
| PENG | 0001616533 | 2025-08-29 | 0001616533-25-000061 | `7f49ae1db8700690e6ea142ddafad7a524e5ab04b5a49e16e5be72bd82ebaca6` |
| ETON | 0001710340 | 2025-12-31 | 0001437749-26-009059 | `f7f154bb5484ead9734e7792fe9226c296b72a5adb5779a7e452499ba4d8b45b` |

## Priority 2 — S8 frozen Ohlson SIZE deflator

The **diagnostic** inventory checks six US-GAAP fields for two annual
endpoints: `Assets`, `Liabilities`, `StockholdersEquity`,
`AssetsCurrent`, `LiabilitiesCurrent`, and `NetIncomeLoss`.
All five companies have **12/12** source-exact diagnostic fact windows in
FY2024/FY2025. This is *not* a claim that all original S8 variables exist.

| Ticker | FY2024 / FY2025 | Diagnostic SEC facts | **Exact blocker** |
|---|---|---:|---|
| INOD | 2024-12-31 / 2025-12-31 | 12/12 | Both GNP price-index points and frozen SIZE base/convention unverified |
| TMDX | 2024-12-31 / 2025-12-31 | 12/12 | Same two dated deflator points/convention |
| CRMD | 2024-12-31 / 2025-12-31 | 12/12 | Same two dated deflator points/convention |
| PENG | 2024-08-30 / 2025-08-29 | 12/12 | Same two issuer fiscal-date deflator points/convention |
| ETON | 2024-12-31 / 2025-12-31 | 12/12 | Same two dated deflator points/convention |

For every ticker the **frozen-contract-compatible Ohlson SIZE price level**
needs an official historical GNP price-index series, the exact required base
year and unit convention, the applicable dated observation(s), and a source
receipt/hash. A generic current CPI/GDP deflator, annual inflation rate, or
arbitrary `1.0` would silently change SIZE and is not accepted.
The issuer-specific funds-from-operations/liabilities classification and
distress binary/change-in-income model inputs are also unverified; CFO is
**not** silently treated as funds from operations. No O-score, probability or
0–100 S8 score is calculated.

## Priority 3 — S10 frozen five-year residual / historical peers

The read-only inventory checks seven *diagnostic* USD concept families in
**FY2021–FY2025**: assets, net income, operating cash flow, current assets,
current liabilities, current receivables and net PP&E. Older periods require
original issuer fiscal-year 10-K evidence. The five fiscal-date anchors for
PENG are 2021-08-27, 2022-08-26, 2023-08-25, 2024-08-30, 2025-08-29;
all four other issuers have calendar-year December 31 anchors.

| Ticker | Exact annual diagnostic facts | Missing issuer-period diagnostic | Missing peer panel |
|---|---:|---|---|
| INOD | 35/35 | None in this limited GAAP inventory | FY2021, 2022, 2023, 2024, 2025 |
| TMDX | 35/35 | None in this limited GAAP inventory | FY2021, 2022, 2023, 2024, 2025 |
| CRMD | **32/35** | `AccountsReceivableNetCurrent` in FY2021, FY2022, FY2023 original 10-K windows | FY2021, 2022, 2023, 2024, 2025 |
| PENG | 35/35 | None in this limited GAAP inventory | FY2021, 2022, 2023, 2024, 2025 |
| ETON | 35/35 | None in this limited GAAP inventory | FY2021, 2022, 2023, 2024, 2025 |

An absent exact receivables tag is not evidence of zero receivables or zero
accruals; a sourced issuer-specific concept mapping and original filing context
would be needed for CRMD. Even for 35/35 diagnostic completeness, the original
S10's approved accrual-variable derivation, cash-flow lag/lead convention,
model regression, residual normalization and peer minimum are not established
by these raw data. **No five-year dated historical industry classification
and verified S10-specific peer roster** exists in this local audit package for
any of the five dates/issuers. Current SEC SIC, reconstructed industry labels,
and previous **S11** FY2025 Jones 20-peer cohorts cannot be repurposed as S10
history without the original S10 selection rules and per-year evidence.

To unblock S10: recover the exact external frozen subsection first, then build
verified year-by-year target and peer accession + reported periods + historical
SIC/industry source headers, restore any issuer-specific missing fields, and
independently reproduce the frozen residual and normalization. There is **no
assumed peer count** in this report; S11's 20-peer minimum does not establish
S10's own requirement.

## Code, commands and verification

The independent implementation has no import/write dependency on the
production DB, S8/S10 scoring engines, or the Windows UI:

- `app/scoring_v8_s8_s10.py` — five cached SEC issuer source gates, exact
  fiscal-year inventory, independent hash and missing-input records.
- `scripts/scoring_v8_s8_s10.py` — JSON CLI; default concise missing matrix,
  `--full` includes source record SHA/accession diagnostics.
- `tests/test_scoring_v8_s8_s10.py` — 10 stdlib `unittest` cases covering hash
  tampering, CIK mismatch, wrong accession, period conflicts, absent 10-K input,
  fiscal-year gaps, PENG August fiscal dates, and no scoring.

```powershell
cd E:\M10\.scoring_v8
python scripts/scoring_v8_s8_s10.py
python scripts/scoring_v8_s8_s10.py --full
python -m unittest tests.test_scoring_v8_s8_s10 -v
git status --short
```

**Observed:** five exact ZIP members verified; **S8=0 scores**,
**S10=0 scores**, **network_requests=0**, **10/10 focused stdlib tests pass**.
The connected Python installations did not contain `pytest`; the regression
suite was executed with stdlib `unittest` instead, without installing packages.
The CLI writes no artifact and does not mutate the source archive. Frozen
formulas, existing 15 Research scores, source receipts, live DB and EXE are
outside this task's write scope.
