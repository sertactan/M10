# MERİDYEN V10 — ETON original Dechow S6 potential, not accepted

**11 October 2026.** New deterministic offline research extension; no modifications
to the original S6 contract, previous scoring code, production DB or installer.

## Source-backed numerical finding

The original SHA-pinned ETON SEC Companyfacts file (`CIK0001710340.json`,
SHA-256 `f7f154bb5484ead9734e7792fe9226c296b72a5adb5779a7e452499ba4d8b45b`)
contains exact 2023 annual balance sheet values from accession
`0001437749-25-008136` and 2024/2025 values from accession
`0001437749-26-009059`. The same dates, full FY windows, USD units and exact
cash from stock option exercises all match. Original [2024 10-K](https://www.sec.gov/Archives/edgar/data/1710340/000143774925008136/eton20241231_10k.htm)
and [2025 10-K](https://www.sec.gov/Archives/edgar/data/1710340/000143774926009059/eton20251231_10k.htm)
present the exact consolidated audited balance-sheet rows.

The original frozen S6 contract SHA-256 is
`53dce841fd5ebdfeb00636f327493be1255ea8b60e6df4eadd921a7098813794`.
All six numeric non-RSST original S6 terms (REC, INV, SOFT, cash-sales,
ROA and actual option-exercise proceeds) are evidenced as research inputs.
The separate WC/NCO/FIN original conditions still require peer-appropriate
short/long financial investments **STI/LTI**, current/noncurrent debt **DLC/DLTT**,
preferred financing **PREF**, and a source-reviewed decomposition. The audited
SEC original accounts support 2023/24/25 current and noncurrent debt figures,
but the absence of separately tagged STI/LTI/PREF is not automatically proof
of zero positions hidden in other asset/liability classifications.

The algebraic **RSST aggregate diagnostic** does not depend on the unverified
STI/LTI/current debt splits, provided the original definitions are satisfied;
this is not acceptance of each constituent. Independently recomputed from
total assets, cash and total liabilities with an alternative CA/CL expression.

| Exact derived FY2025 diagnostic | Value |
|---|---:|
| RSST aggregate / average assets (unreviewed) | -0.1103205596866 |
| ΔREC / average assets | 0.0760355926461 |
| ΔINV / average assets | 0.0022230543816 |
| SOFT | 0.7148316216862 |
| Δ cash sales | 0.9846739159764 |
| Δ ROA | 0.0161895685941 |
| ISSUE positive source evidence | USD 598,000 stock-option exercise proceeds in FY2025 |
| Original Dechow `L` conditional | -5.18910562108 |
| Original `F_D` conditional | **1.498935724923** |
| Frozen numeric bin if all gates were proven | 70, **conditional diagnostic ONLY** |
| **Accepted new S6 Research score** | **N/A** |

Rounding above is for the report; the private source-generated receipt uses
65-digit Decimal and exact original US-GAAP integer dollar inputs. Conditional
ISSUE requires a second original audited stockholders' equity statement proof
for full acceptance; actual proceeds alone are a documented positive candidate.
The engine sets `S6_score=null`, `accepted_full_research=false`,
`historical_pit=false` regardless of how plausible the diagnostic appears.
No reverse-peer percentile or scoring changes were introduced.

## Replay

`E:/M10/.venv/Scripts/python.exe scripts/scoring_v10_extension_s6.py`
then `... scripts/scoring_v10_extension_s6.py --verify` uses only the pinned
original bulk SEC zip, original frozen source and sealed private report
`E:/M10/.scoring_v10_private/extension_s6/eton_s6_candidate_v1.json`.
Run `python -m unittest tests.test_scoring_v10_extension_s6` for scoped tests.
No network requests, human signatures or updates to the installed application.
