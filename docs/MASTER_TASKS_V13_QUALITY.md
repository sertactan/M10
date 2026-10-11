# V13 quality source recovery: INOD iXBRL

The two existing original INOD 10-K HTML bodies were inspected offline without
changing them. Their accession, source URL, body length and SHA-256 were
checked against the private SEC cache receipts and against independent pinned
digests in `app/scoring_v13_quality_ixbrl.py`. The new private result is
`E:/M10/.master_tasks_v13_private/quality/inod_ixbrl_inventory_v2.json`,
SHA-256 `a107e0e315077362349b82b7daeb090b5339571ccd22cbe94e5e1a52c03ba3c2`.
The earlier `inod_ixbrl_inventory.json` remains untouched.

## New original-source finding

The [FY2024 INOD 10-K](https://www.sec.gov/Archives/edgar/data/903651/000141057825000194/inod-20241231x10k.htm),
accession `0001410578-25-000194`, contains two explicit
`us-gaap:OtherShortTermInvestments` iXBRL instant facts:

| Balance-sheet date | Printed fact | Scale | Decoded USD | Acceptance |
|---|---:|---:|---:|---|
| 2023-12-31 | 14 | 10³ | 14,000 | Original source candidate only |
| 2024-12-31 | 14 | 10³ | 14,000 | Original source candidate only |

The [FY2025 INOD 10-K](https://www.sec.gov/Archives/edgar/data/903651/000110465926020655/inod-20251231x10k.htm),
accession `0001104659-26-020655`, has no watched short-term-investment
iXBRL tag. That absence does **not** establish a FY2025 zero or a complete
STI classification. The 2024 filing also has a 2023 cash-flow fact named
`PaymentsForProceedsFromShortTermInvestments`; it is a flow, not the
investment balance. Both filings have preferred-stock value facts with
`nil="true"`, and a printed preferred-shares-outstanding `none`; neither is
silently converted to a preferred-equity dollar zero. No watched inventory
tag was found in either body; inventory remains unproven, not zero.

This narrows one INOD S6 subfield to exact original filing periods. Full
STI/LTI/DLC/DLTT/PREF account scope and the independent WC/NCO/FIN
partition remain unresolved, as does genuine inventory source evidence.
INOD S6 stays **N/A (5/7 existing)**. INOD B_Q still lacks pure
depreciation and accepted `TOTAL_DEBT` LVGI; S13 is unsigned 0/7. The
unchanged S14 remains **3/6**, retaining the true S11 zero. Task 9 is
`PARTIAL`; Task 10 is `BLOCKED`; newly accepted full Research scores: **0**.

`E:/M10/.venv/Scripts/python.exe scripts/scoring_v13_quality_ixbrl.py --verify`
replays both sources and validates the sealed V2 packet. Four focused tests
pass, including body/receipt tampering, `nil`/`none` rejection and the
missing-is-not-zero rule. The output is a source inventory, not an S6, B_Q,
S13 or S14 score. No private raw SEC body is added to Git.
