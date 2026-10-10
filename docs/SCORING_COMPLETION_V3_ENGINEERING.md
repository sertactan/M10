# MERİDYEN M10 — Scoring Completion V3: financial evidence and research acceptance

**Date:** 2026-10-11 JST. **Branch:** `codex/scoring-completion-v3` in
`E:/M10/.phase30_scoring_completion_v3`; base V2 `657a2b252f3d9ab61c947530bd47fa1a5099e316`.

This is an implementation and local validation record. Do not substitute
synthetic unit-test scores, SEC filing keyword hits, issuer quote snapshots,
partial risk components or researched source provenance for a complete issuer
score. All prior V2 research and production Personal Edition data are preserved.

## A. Completed implementation and actual independent data

1. **Official financial sources, private cache:** Reused the 2,949,045-byte INOD
   Companyfacts response, SHA-256
   `6ccc9dcc93b9c303cee51c166f345350fb16258408c884e2ed5d1231f2741b38`,
   and the original SEC Submissions cache (SHA-256
   `070461656ae36691ad952bd53e529dd48fbb74b8f7191637d3c6bb79e27910f3`).
   Two original SEC 10-K filings were joined by CIK/accession, rather than
   assuming a report-year label is the cash-flow accounting period:
   FY2024 10-K `0001410578-25-000194` (accepted `2025-02-24T19:09:04Z`)
   and FY2025 10-K `0001104659-26-020655` (accepted
   `2026-02-26T22:22:13Z`). FY2023 exact figures came from the FY2024 10-K;
   FY2024–25 comparisons came from the FY2025 10-K. Research retrieval
   times **do not** establish historical PIT provider availability.
2. **New filing-body evidence:** Cache-first, fair-access official SEC HTML
   14/14 primary filing bodies, with per-document SHA-256 receipts: two 10-K,
   two 10-Q, nine 8-K and one 8-K/A. FY2024 10-K SHA-256
   `a2c0241be84173898a65f43480a16346704f6d61786e3ab4feff61886d973031`,
   FY2025 10-K SHA-256
   `2d5dd7f964d0239ea18a982f24e077d1b8e0f08baa73fd28dd66f539d9befba2`.
   Bodies stay in the **private local** `scoring_completion/v3_filing_bodies/`
   cache, not GitHub. Final deterministic offline replay report
   `review3_final.json` SHA-256
   `db80442b3e97b79e4a67f5089ebad32c446443f2e2e50957eae2e0dfc5059df4`.
   A final offline replay corrected its analysis-clock target to the actual
   observation time, `2026-10-10T18:33:11Z` (the former `2026-10-11T23:59:59Z`
   is later than this session's UTC clock). The operative private source packet
   is `review4_observed.json` SHA-256
   `c955ded54668ef028b65938674e1682447af7cf0697d3fd2789f1f685f58f4d9`.
   It independently reverified 14/14 cached SEC bodies with **0 new requests**.
   The final Windows staging receipt is isolated under
   `v3_staging_final_asof_observed/report.json`, with S13 still REVIEW_REQUIRED.
3. **B_Q exact components:** 2024/25 revenue and `DirectOperatingCosts`
   from the official consolidated GAAP operations statement were reconciled
   with the same SEC accession's `GrossProfit` in XBRL. This establishes GMI
   ratio and its clipped 0–1 risk; prior V2 DSRI/AQI/SGAI/TATA retained.
   The original account sources, periods, SHA-256 and review document hash
   are sealed under `v3_quality_confirmed/quality_v3.json`.
   B_Q **5/7 weighted risk legs evidenced** (SGI also evidenced as an
   interaction input). DEPI and LVGI remain N/A; independent serious-flag
   adjudication remains N/A. **No B_Q total score.**
4. **Dechow S6:** New exact-source three-FY join produced four real research
   components: receivables change, soft assets, cash-sales change and ROA
   change. **4/7 model components available.** RSST WC/NCO/FIN, inventory
   change and verified issuance are not completed; no Dechow normalized
   score or ungrounded fallback.
5. **Jones S11 real-source cohort:** 18,799 local security-master entries and
   a 20,440-entry official SEC bulk archive were inspected **read-only**.
   INOD FY2025 target had eight of eight required exact-period SEC accounting
   facts, but `security_classification_history` contains **zero dated rows**;
   a current SIC=7374 SEC Submissions value is not historical FY2025
   classification proof. Qualifying same-industry dated peer observations:
   **0/20**; no OLS beta or actual S11 score. The peer ingestion and
   source-period audit is implemented separately, with an isolated private
   `v3_jones_*/report.json` and digest.
6. **S13:** Actual 14 SEC body documents and source passages for all 7 blocks
   are available in the separate `REVIEW_REQUIRED` record. Passage sources by
   category: `AUD=5`, `RPT=1`, `REC=5`, `DIL=4`, `REV=4`, `ACQ=5`, `GOV=10`
   (counts are documents with matching passages, **not reviewed risk scores**).
   Auditor's revenue-recognition critical audit matter, material customer
   receivables concentration, 2026 board/management disclosure candidates
   require explicit risk rubric adjudication. No absent-keyword `0` risk,
   no keyword-only verified serious flags: **0/7 reviewed blocks**, S13 N/A.
7. **S16-EA:** Ten actual 2026 SEC Form 8-K/8-K/A filings are available
   with accession, accepted-at and full body hash. First public news time,
   provider historical access, certified session calendar and 20+ same-clock
   sessions remain missing. Their SEC acceptance times are **event
   candidates**, not trading alerts: **0 verified alerts**.
8. **Windows research staging:** `app.scoring_completion` verifies the original
   local Companyfacts, SEC Submissions, SHA-sealed V3 receipt, original FY2025
   10-K HTML body and the 14 forensic filing bodies by offline re-extraction.
   `app/ui/scoring_completion_page.py` shows 5-stock, 13-column comparison:
   S14 actual model 2/6; INOD raw B_Q risk inputs 5/7; Dechow research
   components 4/7; S16-E and S16-C separate N/A; source-rich details,
   provider price timestamps, forensic `REVIEW_REQUIRED` and 10 SEC event
   candidates. Complete S7/S12 scores remain nine. Local Qt offscreen staging
   smoke passed using sealed `v3_staging_with_events/report.json`, retained
   V2 source hashes and protected Personal Edition. No EXE deployment.
   Final regenerated `v3_staging_final/report.json` also includes the
   SHA-sealed genuine Jones peer-cohort audit: INOD 8/8 audited current/prior
   raw FY figures, 0/20 dated peers and score N/A. Final PySide6 offscreen
   5-stock / 13-column smoke **PASS**; all B_Q/S6/S11/S13 and S16-EA missing
   gates displayed without numeric promotion.

## B. Real accepted model scores

Research stock prices from existing 2026-10-09 20:00:00–01 UTC cache,
**not** live prices. S7/S12 are independently verified source formula scores;
the remaining fields are still absent (`N/A`).

| Ticker | Cached USD | S7 | S12 | B_Q | S6 | S11 | S13 | S14 | S1–S3 | S15.3 | S16-E | S16-C |
|---|---:|---:|---:|---|---|---|---|---|---|---|---|---|
| INOD | 62.04 | 100.00 | 91.528866 | N/A (5/7 risk) | N/A (4/7 partial) | N/A | N/A | N/A (2/6) | N/A | N/A | N/A | N/A |
| TMDX | 77.87 | 100.00 | 85.403881 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| CRMD | 7.38 | 100.00 | 95.682132 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| PENG | 76.28 | 100.00 | 83.512058 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| ETON | 55.21 | 100.00 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |

**Accepted full current research submodel scores:** prior 9, V3 new 0,
total 9. **Complete S14:** 0. **Full S1–S3/S15.3:** 0.
**S16-C:** 0/22 independently normalized and historically PIT accepted.
**S16-E:** `PENDING_APPROVAL` and not activated. **Canonical:** 0
securities / 0 dates, **WF9 BLOCKED**, **Learning V3 NOT_TRAINED**.

## C. New verified real intermediate financial measurements

| INOD B_Q variable | FY2025/FY2024 exact value | Risk leg accepted? |
|---|---:|---|
| DSRI | 1.124585244035 | Yes: clipped risk 0.249170488070 |
| GMI | 0.995444687340 | Yes: clipped risk 0.0 |
| AQI | 0.598973484042 | Yes: clipped risk 0.0 |
| SGAI | 0.944672876867 | Yes: clipped risk 0.0 |
| TATA | -0.086427075857 | Yes: clipped risk 0.0 |
| SGI | 1.476367028235 | Interaction research; not a seventh risk leg |
| DEPI | N/A | Separate pure depreciation vs capitalized amortization missing |
| LVGI | N/A | Complete interest-bearing borrowings reconciliation missing; zero denominator invalid |

The disclosed line of credit facility was not used during FY2025, but a
zero/not-disclosed historical debt denominator must never be forced to a valid
LVGI. The FY2025 10-K Note 3 describes *depreciation and amortization* of PPE,
not a separately sourced pure depreciation rate. No forbidden zero substitution.

| INOD S6 raw component | Verified derived value | Remaining source |
|---|---:|---|
| Δ Receivables / average assets | 0.131164861971 | Complete |
| Soft assets | 0.465007443963 | Complete |
| Δ Cash sales | 0.487635259290 | Complete with three verified FYs |
| Δ ROA | -0.103359407901 | Complete with three verified FYs |
| RSST WC/NCO/FIN | N/A | Source-consistent reviewed decomposition |
| Δ Inventory | N/A | Exact inventory data or explicit category-independent evidence |
| Issuance | N/A | Equity/debt issuance verified +/- with filed evidence |

**Independent reference constraints:** Original source mathematical
coefficients remain frozen. Risk ratios were computed from SEC XBRL USD values
and exact fiscal windows; numerical tests compare their math with independent
`Decimal` expressions. Synthetic unit tests do **not** count as real issuer scores.

**V3 targeted validation:** 35 tests PASS (`tests.test_scoring_v3_sec_quality`,
`tests.test_scoring_v3_integration`, `tests.test_scoring_v3_sec_filing_evidence`,
`tests.test_scoring_v3_jones_peers`, `tests.test_scoring_completion`,
`tests.test_scoring_completion_ui`). Worker-reviewed focused regression:
13 new + 18 existing Jones tests PASS, 7 new + 14 existing forensic tests PASS.
Previously verified 113 V2 tests were not pointlessly rerun as a whole.

## D. Model evidence and gates (9–18)

| No | Initial status | New real work | End status | Verified evidence / further requirement |
|---|---|---|---|---|
| 9 | PARTIAL | Source-joined GMI and four Dechow components; real S13 filing-source packet; S11 peer extraction | PARTIAL | B_Q 5/7, S6 4/7, S13 0/7 reviewed; Jones target 8/8 financial, dated peers 0/20 |
| 10 | 2/6 | Frozen S14 mandatory leg gate rechecked | BLOCKED — 2/6 | Only actual S7/S12; four other fully accepted legs missing |
| 11 | PARTIAL | Preserved prior DNA/Core48/Control12 source gates | PARTIAL | Core48/Control12 incomplete; dated winner/control H missing |
| 12 | PARTIAL | Three frozen models and sparse normalized input barriers preserved | PARTIAL | Version-specific route and historical magnitude gates absent |
| 13 | PARTIAL | Two 10-K, two 10-Q and ten 8-K/8-K/A bodies validated by bytes/accession | PARTIAL | SEC acceptance known; historical provider first available/PIT unknown |
| 14 | 0/22 | Verified previously captured raw daily volume/momentum/extension coverage | BLOCKED — 0/22 | Independent dated normalized PIT universe not present |
| 15 | PENDING_APPROVAL | Existing prototype remains disabled | PENDING_APPROVAL | Calibration and explicit user authorization |
| 16 | PARTIAL | 10 SEC accepted-at event candidates stored | PARTIAL | 0 alarms; news first publication and 20+ same-clock baseline absent |
| 17 | PARTIAL | Five-stock sealed current research comparison includes new INOD evidence | PARTIAL | 9 full S7/S12 scores; 0 new complete issuer scores |
| 18 | PARTIAL | 13-column Qt offline Windows staging, hashes/blocked data verified | PARTIAL / STAGING PASS | Installed Personal Edition update requires user authorization |

Task-level **DONE 0, PARTIAL 7, BLOCKED 2, PENDING_APPROVAL 1**. This
table is an evidence accounting, not ten newly completed production features.

## E. Security and replay

Protected: `E:/M10` root checkout, previous PR 170–175 code,
`%LOCALAPPDATA%/MeridyenM10Personal`, live `operational.db`, 9.2 GB legacy
database, frozen S15/S16 engines, verified backups, Hermes and all unrelated
worktrees. All new SEC bodies and private `quality_v3.json`/`report.json`
remain under `%LOCALAPPDATA%/S153ResearchTerminal/runtime/scoring_completion/`.
No raw SEC payloads, private reports, JSON stock datasets, API keys or DB files
are included in GitHub changes. CI and local staging are separate from
Personal Edition installation, and no merge was performed.

**Next concrete evidence task:** reconcile pure depreciation and complete
interest-bearing debt in FY2024/25 filing notes for DEPI/LVGI. In parallel,
establish historical SIC and at least 20 actual complete industry-year SEC
peers to test S11 without fabricated OLS. S13 requires independent full
seven-block reviewer adjudication before a numeric score is accepted.

Official filing references:
`https://www.sec.gov/Archives/edgar/data/903651/000110465926020655/inod-20251231x10k.htm`;
`https://www.sec.gov/Archives/edgar/data/903651/000141057825000194/inod-20241231x10k.htm`.
