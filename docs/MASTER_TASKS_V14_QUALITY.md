# V14 Tasks 9–10 — broader INOD iXBRL source census

The original, hash-pinned [FY2025 INOD 10-K](https://www.sec.gov/Archives/edgar/data/903651/000110465926020655/inod-20251231x10k.htm)
and [FY2024 INOD 10-K](https://www.sec.gov/Archives/edgar/data/903651/000141057825000194/inod-20241231x10k.htm)
were replayed against the V13 inventory receipt. The V12 quality acceptance
packet and unsigned S13 expert form were also rechecked. This V14 pass scanned
**every `ix:nonFraction` name** in the two original bodies, broadening the
earlier selected-tag scan. It counted 898 facts / 300 distinct names in FY2025
and 902 facts / 284 distinct names in FY2024.

| Required classification | Source observation | Acceptance decision |
|---|---|---|
| STI/LTI | FY2024 original body has two `OtherShortTermInvestments` instant candidates, $14,000 at each FY2023/2024 end. FY2025 has no corresponding tagged balance; neither filing has a tagged `LongTermInvestments` name in this census. | STI/LTI accounting scope and FY2025 value unresolved; absent tag is not zero. |
| Inventory | No `ix:nonFraction` concept name containing `inventor` in either body. | No period-matched inventory delta; absent tag is not zero. |
| Preferred | Two `PreferredStockValue` facts in each filing are `nil=true`; the previously printed share count is `none`. | Preferred dollar balance and financing partition unresolved. |
| Pure depreciation | Both bodies contain `DepreciationDepletionAndAmortization`, but no exact `us-gaap:Depreciation` fact. V4 already rejected a residual from total D&A as pure depreciation. | B_Q DEPI unaccepted. |
| Total debt/LVGI | Company-specific `LongTermObligations` tags cover pension and Microsoft license amounts; the previously reconciled totals are not demonstrated interest-bearing debt. | Comparable frozen `TOTAL_DEBT` and zero-denominator treatment unresolved. |
| WC/NCO/FIN | The source census does not classify STI/LTI, DLC/DLTT and PREF or partition RSST. | S6 RSST remains an unaccepted candidate. |
| S13 expert | V12 packet retains 27 source findings, seven required blocks and zero signed blocks. | S13 N/A pending qualified review. |

The private receipt is
`E:/M10/.master_tasks_v14_private/quality/inod_broad_ixbrl_census_v1.json`,
SHA-256 `02d18b62418d1cf37d0e639ab850fe8b28aaa2b8549ac0b2df045dcf373b1188`.
`scripts/scoring_v14_quality_audit.py --verify` checks the original filing
hashes, V13 receipt and V12 quality packet before comparing the sealed V14
result. Four targeted tests cover the exact census, absent-is-not-zero rule,
source tampering and unsigned expert packet. The local census cannot prove
that an untagged line is economically absent; no zero is inferred from it.

**INOD S6 remains N/A (5/7 inputs), B_Q remains N/A (5/7 risk legs), S13
remains N/A (0/7 signed), and S14 remains N/A (3/6 accepted, including S11's
true zero). Task 9 stays PARTIAL; Task 10 stays BLOCKED. No new full Research
score or mandatory acceptance gate closes.**
