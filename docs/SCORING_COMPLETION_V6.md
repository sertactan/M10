# Scoring Completion V6 — real Research score expansion

V6 continues draft PR #179 at `5485d51416d8ba741fab6a546ec0faf9adce451d` in an isolated worktree. It adds **two** complete FY2025 Modified Jones S11 Research scores to the ten already accepted. The sealed five-stock report has **12** complete Research sub-scores, zero canonical PIT acceptances, and no complete S14. These scores do not claim historical point-in-time admissibility.

| Ticker | Historical 10-K accession | FY end | SIC in that filing | Verified independent peers | S11 / 100 | Decision |
|---|---|---|---:|---:|---:|---|
| INOD | Preserved V4 evidence | 2025-12-31 | 7374 | 20 | 0.000000 | Preserved real score |
| ETON | `0001437749-26-009059` | 2025-12-31 | 2834 | 20 | 7.860332129752234 | `REAL_SCORE_ACCEPTED_RESEARCH` |
| CRMD | `0001213900-26-023889` | 2025-12-31 | 2834 | 20 | 86.01535933860907 | `REAL_SCORE_ACCEPTED_RESEARCH` |
| TMDX | `0001193125-26-067032` | 2025-12-31 | 3845 | 12 | N/A | `DATA_MISSING`: fewer than 20 eligible peers |
| PENG | `0001616533-25-000061` | 2025-08-29 | 3674 | 1 | N/A | `DATA_MISSING`: fewer than 20 eligible peers |

The ETON and CRMD calculations use the original eight SEC GAAP fields, original industry/fiscal-period matching and 20-company minimum, rank-three OLS, and original absolute-discretionary-accrual normalization. The original QR result is independently checked by a 60-digit Decimal normal-equations calculation. Acceptance replays the **original cached SEC response bytes offline** and checks the target, 20 distinct peers, filing headers, Companyfacts fingerprints, model components, normalisation, receipt seal, and zero network calls. ETON uses `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax`; CRMD's filed annual revenue uses the official `us-gaap:Revenues` tag. This tag selection changes neither the Jones model nor the peer threshold.

PENG's 2025 annual period ends on August 29; the cohort selector now accepts the filing's actual fiscal-year anchor instead of implicitly treating it as a December filer. The FY2025 10-K header identifies SIC 3674. The official SIC directory and local SEC bulk archive produced two exact-field precheck candidates, of which one qualified after historical filing verification. TMDX's SIC 3845 search produced 13 exact-field precheck candidates and 12 verified peers. A second pass across six standard GAAP revenue concepts in the local SIC3845 archive found only 17 unique exact-field CIKs. Neither company meets the frozen 20-peer gate. No coefficients or scores were imputed. Candidate receipts are private, sealed, and remain outside Git.

Private source receipt SHA-256 values: ETON `0f4a5e61fa79dcef82f19188e2c3413aefb01794dc02fd751db44bb8123b27fe`; CRMD `806c7f33ada4cc2fbda256da284473b58ad72b81a8ef8b9e989c13c71ccd3b55`; TMDX `9db42edfbac5940681c08fa5a8aadfc68d452e8712e548f95e5d7058a5`; PENG `eb03b2a16366fb6836def74f725022af7136280acd9a68f1d06f8da301451c76`. Their local paths are under `E:/M10/.scoring_v6_private/jones_<ticker>/report.json`, with separate `.sha256` seals. The accepted ETON and CRMD report is `E:/M10/.scoring_v6_private/scoring_completion/crmd_s11/report.json`. It loads only while private source receipts and staging database fingerprints still match.

## Remaining model gates

V5's source inventory was reused; no earlier accepted input was changed. INOD S6 retains 5/7 accepted inputs. Its RSST candidate is `0.059140128066`, but STI/LTI/DLC/DLTT decomposition is not proven and Inventory is absent, so S6 remains `DATA_MISSING`. B_Q retains 5/7; pure depreciation/DEPI and comparable interest-bearing debt/LVGI lack sufficient evidence. A zero prior-year debt denominator is a conditional `SPEC_EDGE_CASE`, not permission to alter the frozen formula. No new qualifying official accounting evidence was found in this V6 score expansion. The proposed treatment would require a separately approved, versioned specification.

S13's 14 verified SEC bodies, 27 contextual findings and unsigned seven-section expert form remain intact at `E:/M10/.scoring_v5_private/s13/s13_expert_form_v5.json`. AUD, RPT, REC, DIL, REV, ACQ and GOV remain 0/7 **completed decisions** and `REVIEW_REQUIRED`; no serious flag was assigned without a signed materiality and duplication judgment. INOD S14 is N/A at 3/6, with the real zero S11 included. CRMD S14 is N/A at 3/6; ETON S14 is N/A at 2/6. No missing component was replaced by zero or a neutral value.

Existing S1–S3 evidence lacks full Core48/Control12/H gates. S15.3 remains inconclusive, S16-C has 0/22 normalized accepted PIT features, S16-E awaits calibration/approval, and S16-EA lacks first-publication timestamps and same-clock history. No other independent model was promoted without its complete frozen specification and inputs.

## Validation and delivery

The targeted Jones/cohort regressions pass (43 tests). Windows Qt offscreen staging passes with five stocks, fourteen comparison columns, 12 complete Research scores, INOD S11 rendered as true 0.00, ETON/CRMD S11 rendered as above, S14 N/A and canonical zero. The window closes cleanly. The installed Personal Edition, live operational database, 9.2 GB historical database, backups, frozen formulas and prior PRs were not modified. Private SEC response bytes and staging reports are excluded from Git.

Tasks 9, 11–13, 16–17 are **PARTIAL**; tasks 10 and 14 are **BLOCKED** for full-score acceptance; task 15 is **PENDING_APPROVAL**; task 18 staging is **DONE**, production deployment is not requested. The substantive V6 gain is two new fully calculated S11 Research scores.
