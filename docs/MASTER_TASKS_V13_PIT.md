# V13 Tasks 13, 14 and 16: SEC/PIT accession reconciliation

## Real evidence closed

Seven INOD financial filings in the existing Phase24K and Phase24M private
reports were independently joined to the **sealed SEC Submissions response**
for CIK `0000903651`. The response receipt reports HTTP 200, 162,393 bytes,
retrieved 2026-10-10 17:11:52 UTC. Its original byte SHA-256 replayed as
`070461656ae36691ad952bd53e529dd48fbb74b8f7191637d3c6bb79e27910f3`.
For every accession, SEC form, official filing date and UTC acceptance
timestamp match both earlier reports exactly. The 7/7 administrative clock
join is now checked against primary captured bytes, not solely between the
two derived reports.

| Accession | Form | SEC accepted UTC | Historical public/provider time |
|---|---|---|---|
| `0001410578-24-000124` | 10-K | 2024-03-04 17:55:46 | Unknown |
| `0001410578-24-000611` | 10-Q | 2024-05-07 21:48:33 | Unknown |
| `0001410578-24-001246` | 10-Q | 2024-08-08 22:00:33 | Unknown |
| `0001410578-24-001800` | 10-Q | 2024-11-07 22:01:07 | Unknown |
| `0001410578-25-000194` | 10-K | 2025-02-24 19:09:04 | Unknown |
| `0001410578-25-001113` | 10-Q | 2025-05-08 21:49:06 | Unknown |
| `0001410578-25-001550` | 10-Q | 2025-07-31 21:30:56 | Unknown |

Read-only output and exact SHA sidecar:
`E:/M10/.master_tasks_v13_private/pit/inod_seven_accession_reconciliation.json`
and `.json.sha256`. Report digest:
`1fb974624963696d9a46f9f238f013fe4d64133ba45a17a144f84e239f7afeff`.
Run `python -B scripts/scoring_v13_pit_reconcile.py --help` for the four
private source arguments; use `--verify` to replay all original bytes and
compare the existing report and sidecar without replacing them. The source
reports' byte hashes are included in the private output.

## Remaining acceptance gates

The seven matched SEC acceptance values remain **administrative evidence**.
The 2026 retrieval cannot establish when the market first received a filing
in 2024–2025 or when a historical provider first captured its facts. Neither
Phase24K nor Phase24M certifies historical issuer/share-class mapping or
actual dissemination. `first_public_at` and
`historical_provider_first_available_at` therefore remain null on all seven
rows. Task 13 is PARTIAL; **canonical PIT versions: 0**.

S16-C requires 22 real source-defined features, each available by its as-of
clock and normalized against a genuine same-date cross-sectional universe.
No SEC administrative join is a normalized S16-C feature. Task 14 remains
BLOCKED, **0/22**; no score or WF9 admission follows.

The earlier S16-EA intraday probe's original `response.json` SHA matches its
receipt `6f3746effd4dad60c5944a65b7c6f989757e61f14cd5772475cefd176bd400f1`.
Its derived `bars.json` contains 2,126 one-minute and 218 complete derived
five-minute rows over five ET dates, with 254 premarket-clock rows in the
receipt. `bars.json` is not the receipt-hashed original response. The receipt
explicitly records `news_first_public_time=null`, no validated same-clock
baseline, no validated exchange calendar, and no alert. Five dates cannot
satisfy the previously specified 20-session baseline. Task 16 remains
PARTIAL, **0 verified alerts**. A contemporaneous first-news feed, source
arrival logs, complete same-clock OHLCV history and matured hit/miss/false
positive evaluation are still needed.

## Tests and scope

The V13 reconciliation rejects mismatched response bytes, mismatched CIK,
duplicate/missing accessions, tampered form/date/acceptance fields and any
upstream canonical claim. Tests use artificial fixtures solely to verify
software gates. No private SEC bytes, live database, old worktree, frozen
model, score or installed application was changed.
