# V14 Tasks 13–14: INOD filing-version diagnostic

## Source replay

Seven historical INOD financial accessions retain the V13 7/7 SEC
administrative form, filing-date and acceptance-time joins. V14 additionally
checked two cached 10-K HTML bodies against their byte receipts, embedded
iXBRL facts, the current SEC Companyfacts snapshot, and the sealed SEC
Submissions response. The private report is
`E:/M10/.master_tasks_v14_private/pit/inod_versions_v1.json`; its replayed
SHA-256 is
`504497b2cea46ba6612dc53e14661182b975d67f295e58603e37f8b6a3734471`.
The adjacent `.sha256` sidecar matched a second read-only replay.

| FY2024 comparative fact | 2024 10-K, accepted 2025-02-24 19:09:04 UTC | 2025 10-K, accepted 2026-02-26 22:22:13 UTC |
|---|---:|---:|
| Cash and cash equivalents | $46,883,000 | $46,897,000 |
| Allowance for doubtful accounts receivable | $1,759,000 | $1,256,000 |

Both 10-K bodies carry CIK `0000903651`, ticker `INOD`, Common Stock, and
Nasdaq identity tags. The current Submissions snapshot contains no `10-K/A`
or `10-Q/A` row for these two report periods; the scan is limited to this
captured snapshot. The changed comparative values are **not proof of a formal
restatement**. The HTML receipts explicitly mark independent source
authenticity `false` and were retrieved 2026-10-10; this further limits
historical claims.

The March 2025 diagnostic admits only the 2024 10-K under an **SEC
administrative acceptance clock**. The March 2026 diagnostic lists both.
Neither is a canonical as-of replay: historical first-publication timestamps,
provider first-available logs, a daily issuer/share-class map, and complete
original/amended chains for all seven accessions remain unavailable. SEC
accepted-at is not substituted for provider available-at. Thus
`13.available_at`, `13.versioning`, `13.issuer_mapping`, and `13.replay` remain
**OPEN**. The two filing-level identity anchors are narrower than the
`13.issuer_mapping` requirement.

No PIT-certified, dated, cross-sectionally normalized S16-C feature follows
from these facts. Task 14 remains **BLOCKED**, with **0/22** canonical features
and no score. V13's 14/40 verified-gate checkpoint is unchanged by this
diagnostic. Five contract tests passed and the real-source private replay
passed twice (creation and exact-byte verification).

The source hashes, original accessions, body receipt hashes and as-of
diagnostics are recorded in the private report. No raw SEC response or filing
body is committed here.
