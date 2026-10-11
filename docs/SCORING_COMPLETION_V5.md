# Scoring Completion V5 — RSST partition boundary

Date: 2026-10-11 JST. Based on V4 PR #178 at `b072756e0479429f9b0251cc7c38345e31ab0f80`.
This is current Research evidence only. New complete stock/model scores: **0**;
five-stock total remains **10**. INOD S14 remains **N/A, 3/6**.

## Source-bound finding

`app/scoring_v5_dechow.py` replays the V4 hash-pinned SEC Companyfacts and
FY2024/25 original 10-Ks, then selects exact accession-matched current assets
and current liabilities for FY2023–25. Each newly selected fact, including its
SEC accession, period and record digest, is preserved in the private receipt.
The FY2024/25 comparative figures use the same FY2025 accession as the V4 RSST
aggregate. Source: [INOD FY2025 10-K](https://www.sec.gov/Archives/edgar/data/903651/000110465926020655/inod-20251231x10k.htm),
SHA-256 `2d5dd7f964d0239ea18a982f24e077d1b8e0f08baa73fd28dd66f539d9befba2`.
The prior-year check uses the [FY2024 10-K](https://www.sec.gov/Archives/edgar/data/903651/000141057825000194/inod-20241231x10k.htm),
SHA-256 `a2c0241be84173898a65f43480a16346704f6d61786e3ab4feff61886d973031`.

| USD | FY2023 | FY2024 | FY2025 |
|---|---:|---:|---:|
| WC base = CA − cash − CL | -4,664,000 | -5,403,000 | 2,632,000 |
| NCO base = TA − CA − TL + CL | 15,853,000 | 21,895,000 | 22,200,000 |

The original definitions require `WC = WC base − STI + DLC`,
`NCO = NCO base − LTI + DLTT`, and
`FIN = STI + LTI − DLTT − DLC − PREF`.
STI/LTI/DLC/DLTT require independent issuer-period classification. They cancel
algebraically, so the V4 aggregate remains correct, but cancellation does not
attest individual WC/NCO/FIN inputs. The original frozen `decomposition_review`
gate is therefore unsatisfied. The source-verified aggregate RSST candidate
remains `0.05914012806603271853128257494`; **RSST is not frozen accepted**.
Private receipt SHA-256:
`c3fb849fa6fc026385de7332affa33df73227dfd9f4c708fdb402ac0d8df10eb`.

The annual SEC Companyfacts and inline XBRL search still yield no FY2024/25
inventory amount or affirmative zero; the balance sheet combines prepaid and
other current assets. The source specification provides no missing-inventory
exception. S6 is `DATA_MISSING`, with 5/7 accepted inputs and this one RSST
aggregate candidate. No normalization or S6 score is run.

## B_Q, S13 and independent models

The 2025 10-K's cash flow table displays **payment of long-term obligations**
of USD420k/362k for FY2025/24; its inline GAAP tag is
`RepaymentsOfLongTermDebt`. Note 6 reports Microsoft license obligations of
USD6k/442k and pension obligations of USD9.278m/7.945m. The filing states the
Wells Fargo revolver was unused in FY2025. A cash-flow taxonomy name and a
combined obligation balance cannot establish comparable **interest-bearing**
debt for frozen LVGI. If a properly classified prior-year debt denominator is
zero, the original positive-denominator requirement makes LVGI a
`SPEC_EDGE_CASE`; the evidence does not currently certify that zero. LVGI and
B_Q remain `DATA_MISSING` (5/7). Pure depreciation remains unseparated from
amortization, so DEPI is also missing. No frozen formula was changed.

The hash-sealed V4 forensic packet still has 27 findings from 14 SEC bodies and
0/7 independent numeric decisions. V5 creates an **unsigned** private expert
form with seven sections, each carrying source accession, section, hash,
mitigating/adverse context, and explicit blank materiality, risk, serious-flag,
duplicate-event, reviewer and date fields. It does not convert contextual SEC
disclosures into signed decisions. S13 remains `REVIEW_REQUIRED`, S14 N/A.
Private unsigned form SHA-256:
`11dba0a6c2bf6ac2d9c34c78ee4e36ae4a96a8c81c8f048f4e4546e7cf907e7f`.

The existing five-stock report was inspected. S7 and S12 are complete for INOD,
TMDX, CRMD and PENG; ETON has S7, while S12 remains partial because its annual
net income fails the positive-income requirement. Only INOD has the source
verified full S11 Modified Jones score (a real **0.00**). Applying S11 to other
stocks would need separate dated industry-year peer cohorts; the INOD SIC7374
cohort cannot be reused. S1–S3 lack full Core48/Control12/H evidence; S15.3
remains inconclusive; S16-C is 0/22 normalized accepted features; S16-E needs
calibration/approval; S16-EA lacks first-published news and same-clock history.
No existing partial result was promoted.

## Acceptance and delivery

S6 `DATA_MISSING`; B_Q `DATA_MISSING` with conditional LVGI
`SPEC_EDGE_CASE`; S13 `REVIEW_REQUIRED`; S14 `DATA_MISSING` at 3/6.
Tasks 9, 11–13 and 16–17 remain PARTIAL; tasks 10 and 14 are BLOCKED for
complete model acceptance; task 15 remains PENDING_APPROVAL; task 18 has a
passing staging check while production acceptance remains pending. No task
9–18 is end-to-end DONE.
Historical canonical acceptance remains zero securities/dates.

The private V5 receipts are under `E:/M10/.scoring_v5_private/` and are not
part of Git. Only source replay code, focused gates and this report are in the
branch. Live Personal Edition, operational database, older databases, backups,
frozen model modules and PR #178 remain untouched.
Targeted local regression: 35 tests PASS. Qt offscreen Windows staging: PASS,
five stocks, 14 columns, ten full Research scores, S11=0.00, S14=N/A,
canonical zero, clean window close. The UI is unchanged in V5.
