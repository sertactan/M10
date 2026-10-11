# V10 quality evidence — genuine Beneish DEPI component, no whole-model promotion

This is an isolated extension of V9 (HEAD `389c83a`). It does **not** modify
frozen formulas, research baselines, the user-installed app or private sources.
The original `S1_S2_S14_CANONICAL_SOURCE.md` has SHA-256
`53dce841fd5ebdfeb00636f327493be1255ea8b60e6df4eadd921a7098813794`;
its original S5/B_Q pure-depreciation **DEPI** is
`(Dep[t-1]/(Dep[t-1]+PPE[t-1])) / (Dep[t]/(Dep[t]+PPE[t]))` and
`R_DEPI=clip((DEPI−1)/0.75, 0, 1)`.

## Actual new sourced component observations

The original SEC bulk Companyfacts ZIP member, issuer CIK, **exact FY2025 10-K accession**, comparative FY2024 period, strict `us-gaap:Depreciation` (not D&A), strict `us-gaap:PropertyPlantAndEquipmentNet`, `USD` unit, record SHA and pinned source ZIP-member SHA are independently verified on **every offline replay**. The latest filed period is FY2025, and each FY2024 comparative is selected from the same exact FY2025 filing. The source recorded filing dates are respected; no as-of historical PIT claim is made.

| Issuer | FY2025 original accession | 2025 pure depreciation | 2024 pure depreciation | 2025 PPE net | 2024 PPE net | DEPI ratio | R_DEPI |
|---|---|---:|---:|---:|---:|---:|---:|
| CRMD | `0001213900-26-023889` | $677,000 | $154,000 | $5,959,000 | $1,829,000 | 0.761229684221 | 0.000000 |
| ETON | `0001437749-26-009059` | $41,000 | $50,000 | $326,000 | $34,000 | 5.328106852497 | 1.000000 |
| PENG | `0001616533-25-000061` | $20,579,000 | $25,720,000 | $92,603,000 | $106,548,000 | 1.069471644355 | 0.092628859140 |
| TMDX | `0001193125-26-067032` | N/A | N/A | $327,656,000 | $285,970,000 | N/A | N/A |
| INOD | `0001104659-26-020655` | N/A | N/A | $7,966,000 | $4,101,000 | N/A | N/A |

**Those three real DEPI values are only individual risk components, not complete B_Q/S5 scores.** INOD and TMDX file a broader `DepreciationDepletionAndAmortization` XBRL concept; that cannot establish pure depreciation. CRMD's separate capitalized intangible amortization from V9 is not counted as depreciation. The second arithmetic reference uses the cross-multiplied numerator/denominator with 60-digit Decimal; the worst tolerance is <1e-50. Original FY2025 10-K financial statement rows (not the latest price) define scope.

## INOD remaining frozen quality blockers

- **B_Q: 5/7**, DEPI still unsourced and LVGI (`(Debt_t/Assets_t)/(Debt_p/Assets_p)`) requires its own definition of `TotalDebt`. V9's real **zero FY2025 / zero FY2024 long-term interest-bearing bank borrowing** is not a proven equivalent of B_Q `TotalDebt`. *Conditional* 0/0 would be `SPEC_EDGE_CASE` with a genuinely matched definition; never set LVGI to zero, one or an epsilon ratio. Documented here as a **conditional**, not a new accepted Beneish gate.
- **S6: 5/7**, independently necessary RSST WC/NCO/FIN partition uses STI/LTI/DLC/DLTT and inventory changes, missing genuine filed definitions. V9's S9 bank borrowing scope is insufficient for S6 debt partition. Candidate aggregate RSST **0.059140128066** remains unaccepted; absence of an inventory row is not proof of zero.
- **S13: REVIEW_REQUIRED**, the source-pinned seven-category `s13_expert_form_v5.json` is still unsigned **0/7**, with original 27 findings and no independent serious-flag judgments. No automated signature or seriousness/materiality level may be assigned.
- **INOD S14: 3/6**, accepted S7=100, S11=**0 true numeric**, S12=91.528866 remain. S6/B_Q/S13 not accepted. Original geometric S14 cannot be evaluated with missing legs, even though the S11 zero is a real input.

Implementation: `app/scoring_v10_quality.py` and `scripts/scoring_v10_quality.py`; original SEC/INOD V9 receipt and unsigned expert form verified by private seals. Run offline `E:/M10/.venv/Scripts/python.exe scripts/scoring_v10_quality.py` from the V10 checkout; it stores only `E:/M10/.scoring_v10_private/quality/component_evidence_v2.json` plus separate SHA seal. The initial diagnostic `component_evidence.json` receipt remains untouched. V2 also validates the original locally installed frozen model source SHA in addition to its constant. The existing private report recomputes and compares exact bytes, detecting changed source receipts. Code has no network access, cannot sign S13 or write live DB. Tests in `tests/test_scoring_v10_quality.py` include real original SEC cache tests (skipped in GitHub public CI if Windows cache unavailable).

Initial offline diagnosis receipt SHA-256: `29e1900c127032319ba39c866a6c94c996acd4250c364c5e2b8a273a897ff96e`; frozen-source-pinned V2 receipt digest is printed by the script.
