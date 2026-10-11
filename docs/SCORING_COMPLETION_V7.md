# Scoring Completion V7 — Research score acceptance and Task 9–18 status

V7 continues the five-stock Research snapshot from V6. It preserves all 12 accepted S7/S11/S12 results and adds three FY2025 Piotroski S9 scores after checking the original nine-signal formula, exact SEC Companyfacts periods and accessions, official 10-K bodies, and an independent 60-digit Decimal reference. The sealed staging snapshot contains 15 full Research submodel scores; canonical and historical PIT accepted counts remain zero.

## V7 model acceptance matrix

| Candidate | Frozen contract | Inputs and source | Independent check | V7 decision |
|---|---|---|---|---|
| S1–S3 | Recovered contracts remain the V1–V6 contracts; full Core48/Control12/H gates are required | Existing evidence does not cover the full input sets | Cannot calculate complete scores from current evidence | `DATA_MISSING`; no new score |
| S4 / S5 | Beneish ratios and frozen gates remain unchanged | DEPI needs pure depreciation; LVGI needs comparable interest-bearing debt. Existing evidence does not resolve either across the five issuers | Not eligible | `DATA_MISSING`; no new score |
| S8 | Frozen Ohlson contract unchanged | Complete exact inputs and required SIZE deflator are not yet evidenced | Not eligible | `DATA_MISSING`; no new score |
| S9 | Piotroski F-Score, nine binary signals, score = 100 × signal count / 9; source contract SHA-256 `53dce841fd5ebdfeb00636f327493be1255ea8b60e6df4eadd921a7098813794` | Official SEC Companyfacts, current and prior 10-K periods, exact accessions and issuer-specific tag/debt mappings; official current 10-K body checked for issuer, filing type, issuance and documented zero debt | Independent Decimal re-performance, sealed source receipts, and offline replay on report load all pass | TMDX 77.777778, PENG 66.666667, ETON 55.555556 accepted Research-only; CRMD and INOD remain N/A because the new evidence package did not establish all S9 inputs for them |
| S10 | Frozen residual-quality contract unchanged | Five-year issuer history and eligible industry peer panel unavailable | Not eligible | `DATA_MISSING`; no new score |
| S15.3 V1.2 | Frozen version gates unchanged | `S15.2`, M10 ≥5/7, T10 ≥5/7 and route coverage are incomplete | Not eligible | `DATA_MISSING`; no full score |
| S15.3 V1.4 | Frozen version gates unchanged | Required V1.4 feature, route and evidence gates remain incomplete | Not eligible | `DATA_MISSING`; no full score |
| S15.3 V1.4.1 | Frozen version gates unchanged | V1.2 readiness prerequisite not satisfied | Not eligible | `DATA_MISSING`; no full score |

The S9 formula is the original Piotroski nine-signal model described in the [original study hosted by Ivey](https://www.ivey.uwo.ca/media/3775523/value_investing_the_use_of_historical_financial_statement_information.pdf). Data were drawn from SEC submissions and Companyfacts and matched to the filed 10-Ks: [TMDX](https://www.sec.gov/Archives/edgar/data/1756262/000119312526067032/tmdx-20251231.htm), [PENG](https://www.sec.gov/Archives/edgar/data/1616533/000161653325000061/peng-20250829.htm), and [ETON](https://www.sec.gov/Archives/edgar/data/1710340/000143774926009059/eton20251231_10k.htm). TMDX is FY ended 2025-12-31, accession `0001193125-26-067032`; PENG is FY ended 2025-08-29, accession `0001616533-25-000061`; ETON is FY ended 2025-12-31, accession `0001437749-26-009059`. Private response bodies and receipt seals stay outside Git.

The additional accepted scores are Research calculations only. This V7 work does not backdate their public availability or promote them to canonical PIT observations. S9 values are 7/9 for TMDX, 6/9 for PENG, and 5/9 for ETON. The three zero/new missing distinctions remain explicit: TMDX and PENG S11 are still N/A because their verified peer counts remain 12 and 1 against a frozen minimum of 20; INOD S11 remains a genuine 0.00.

## Preserved five-stock score matrix

| Ticker | S7 | S11 | S12 | New S9 | S14 |
|---|---:|---:|---:|---:|---|
| INOD | 100.000000 | 0.000000 | 91.528866 | N/A | N/A, 3/6 |
| TMDX | 100.000000 | N/A | 85.403881 | 77.777778 | N/A |
| CRMD | 100.000000 | 86.015359 | 95.682132 | N/A | N/A, 3/6 |
| PENG | 100.000000 | N/A | 83.512058 | 66.666667 | N/A |
| ETON | 100.000000 | 7.860332 | N/A | 55.555556 | N/A, 2/6 |

## Remaining component work under Task 9

INOD S6 remains 5/7. The RSST candidate remains `0.059140128066`; it is not a frozen accepted input because STI/LTI/DLC/DLTT class evidence is incomplete. Inventory remains unavailable and is not treated as zero. B_Q remains 5/7: pure depreciation for DEPI and comparable interest-bearing debt for LVGI are unresolved. Any actual zero prior debt denominator remains `SPEC_EDGE_CASE`; the frozen formula is not changed. S13 remains `REVIEW_REQUIRED` with 0/7 signed decisions. The seven risk categories still need independently signed reviewer decisions with materiality, evidence, serious-flag and duplication rationale. Accordingly, INOD S14 remains N/A at 3/6, with its true zero S11 preserved. No S14 score was filled from missing components.

## Master Task 9–18 status

| Task | Status | What remains for DONE |
|---|---|---|
| 9 — S14 quality components | PARTIAL | Complete and accept missing S6, B_Q and S13 components; preserve separate accounting and human-review gates |
| 10 — INOD first full S14 | BLOCKED | Accepted S6, B_Q and S13 scores, then frozen geometric aggregation and integration |
| 11 — S1–S3 full scores | PARTIAL | Complete frozen Core48/Control12/H input gates, exact real data and full-score independent checks |
| 12 — S15.3 three versions | PARTIAL | Satisfy each version's frozen gates and verify all three complete versions |
| 13 — SEC/PIT historical source evidence | PARTIAL | Establish point-in-time source availability and admissible histories for every claimed historical feature; current Research receipts are not PIT proof |
| 14 — S16-C 22/22 canonical features | BLOCKED | Accept all 22 PIT-normalized features from admissible historical sources; currently 0/22 |
| 15 — S16-E calibration and user approval | PENDING_APPROVAL | Complete real-data calibration and receive explicit user activation approval |
| 16 — S16-EA early warning | PARTIAL | Validate original publication timestamps and same-clock historical replay |
| 17 — five-stock full model comparison | PARTIAL | Expand beyond the 15 complete submodel scores; satisfy remaining complete model contracts and show final comparison |
| 18 — Windows Personal Edition final acceptance | PARTIAL | V7 staging smoke passed; separate final installed-edition acceptance is still required |

## Verification and scope

The V7 sealed report preserves the V6 twelve-score baseline, adds exactly three S9 scores, reports 15 total complete Research scores, and retains `canonical_securities=0`. The report loader independently replays S9 receipts offline and rejects changed source bytes, accession bindings, output values or receipt seals. Windows Qt staging passed with five stocks, 15 columns, three visible S9 scores, the real INOD S11 zero, S14 still N/A, and a cleanly closed window. The live installed Personal Edition, operational database, historical database, backups, V6 sources and prior PRs were not changed. S16-E approval remains a distinct user decision; no activation or production deployment is included.
