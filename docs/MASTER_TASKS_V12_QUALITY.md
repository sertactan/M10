# V12 quality acceptance: Master Tasks 9 and 10

This is an offline acceptance audit of original-source Research evidence. The frozen
S1–S14 source remains SHA-256
`53dce841fd5ebdfeb00636f327493be1255ea8b60e6df4eadd921a7098813794`.
The original S5/B_Q, S6 and S13 definitions are recovered in
`docs/RECOVERED_QUALITY_CONTRACTS.md`; the unchanged six-leg S14 gate is
`core/scoring/s1_s14.py:s14`. The private V12 decision packet is
`E:/M10/.master_tasks_v12_private/quality/acceptance_audit_v2.json`, sealed
with SHA-256 `c29b189ecaf3018963ee58b5ffe1524ad085536855755f3e06e8eb06c0b32c8b`.
It is reproduced from pinned SEC Companyfacts, the V9 INOD S9 receipt, the
V4 forensic parent packet and the V5 unsigned expert form. No SEC network
request, production database write, or scoring promotion occurs.

## Task 9: original acceptance gates

| Component | Verified V12 action | Still required for acceptance |
|---|---|---|
| INOD S6 | V10 5/7 evidence retained; candidate RSST 0.059140128066 stays unaccepted. | Original inventory and STI/LTI/DLC/DLTT classification; independent WC/NCO/FIN partition and normalization. No absent-row-as-zero. |
| ETON S6 | Exact pinned FY2023–25 Companyfacts and original frozen source replay; conditional F_D `1.49893572492284258…`, conditional 70 bin only. FY2025 $598,000 option exercise and FY2023–25 debt evidence retained from V11. | Source-bound STI/LTI/PREF, independent WC/NCO/FIN review, original filing byte seals and final normalization. |
| CRMD B_Q | Original FY2025 10-K accession `0001213900-26-023889`, both FY periods rechecked. Pure DEPI `0.761229684221…` retained. Exact standard candidate rows 8/12 per year; original same-accession `Revenues`, `GeneralAndAdministrativeExpense`, and `SellingAndMarketingExpense` rows surfaced for filing-specific mapping. | Revenue/SGA definition, convertible debt scope across both periods, all seven risk ratios and independent serious-flag review. |
| ETON B_Q | Original FY2025 accession `0001437749-26-009059`, 10/12 exact candidate rows per year, pure DEPI `5.328106852497…`. Same-accession `CostOfGoodsAndServicesSold` and `GeneralAndAdministrativeExpense` in both periods surfaced. | Determine whether these lines fulfill original COGS/SGA definitions; review TOTAL_DEBT scope and flags. |
| PENG B_Q | Original FY2025 accession `0001616533-25-000061` with August FY boundary, 11/12 exact candidate rows per year, pure DEPI `1.069471644355…`. Same-accession `CostOfGoodsAndServicesSold` in both periods surfaced. | Verify original COGS scope, TOTAL_DEBT scope and flags. |
| INOD B_Q | Original 5/7 remains; pure depreciation and original TOTAL_DEBT LVGI still unresolved. | A true 0/0 debt ratio is `SPEC_EDGE_CASE`; S9's narrower zero borrowing is no LVGI definition or neutral value. |
| INOD S13 | V5 unsigned form and its V4 sealed parent verified. All 27 finding IDs across AUD/RPT/REC/DIL/REV/ACQ/GOV are source referenced, unique and still unsigned. Parent packet reports 14 official bodies. Decision packet lists each category's findings, context, outstanding question and required signed fields. | Qualified reviewer must decide risk level, materiality, independent serious flags and duplicate issues for **all seven** blocks; then sign with identity/time. No automatic risk level is inferred. |

Exact alternative US-GAAP tag rows in the packet are **candidates**, not accepted
accounting mappings. CRMD's convertible debt candidate appears in only one of
the two exact comparative periods. The presence of a similarly named tag does
not settle the frozen `TOTAL_DEBT` definition. ETON's candidate source is the
sealed Companyfacts member, not a seal of the original 10-K HTML body.

**Task 9 = PARTIAL.** No newly completed S6, B_Q/S5 or S13 score was accepted.
The executable audit narrowed specific B_Q mapping work and assembled a
source-bound S13 review packet; it did not fulfill the original complete gate.

## Task 10: INOD full S14

Accepted existing legs are S7 `100`, S11 **true numeric zero**, S12
`91.528866`. S6, B_Q and S13 are missing; the original aggregator returns
`None` with 3/6 legs. The independent 60-digit Decimal reference also refuses
missing legs and agrees with the frozen aggregator on a complete six-leg
test case containing a true S11 zero. A test case is mathematical validation,
not an INOD score. Once the three missing legs pass their own source gates,
run both calculations on their accepted receipts and then update the Research
report only if they agree. **Task 10 = BLOCKED; INOD S14 = N/A.**

## Replay and reviewer decision

Run `E:/M10/.venv/Scripts/python.exe scripts/scoring_v12_quality_audit.py --verify`
from this worktree. The run checks source seals, frozen-source hash, exact
original SEC accession/CIK/period/USD for candidate rows, S13 finding count,
and INOD S14's missing-leg gate. The packet's review questions point to the
original [INOD FY2025 filing](https://www.sec.gov/Archives/edgar/data/903651/000110465926020655/inod-20251231x10k.htm)
and other SEC references held in the private form.

S13 decision owner: an authorized qualified expert. The valid choices for
each block are the frozen risk levels 0/25/50/75/100, with a written
materiality rationale and independent serious-issue/duplicate review. The
safe current state is `REVIEW_REQUIRED`, `S13=N/A`, `S14=N/A`. Without the
expert decision, Task 9 and hence Task 10 remain open. After a signed form is
supplied, replay its source seal, validate seven decisions and cross-block
independence, calculate S13 using the frozen weights, and run the complete S14
acceptance test only if S6 and B_Q are also accepted.
