# V13 Task 16 — S16-EA event-clock source gate

The existing INOD minute response was replayed from original captured bytes,
SHA-256 `6f3746effd4dad60c5944a65b7c6f989757e61f14cd5772475cefd176bd400f1`.
The saved derivative matches the original parser exactly: **2,126 one-minute
bars**, **218 complete derived five-minute bars**, and **254 premarket-clock
rows**. The source spans five distinct US Eastern dates, 5–9 October 2026.
Its capture occurred 10 October 2026 at 17:19:49 UTC; that retrospective
capture does not establish when a provider first supplied any bar.

The last date has at most **four prior same-clock dates** in the cached
window. The existing research threshold is 20 prior sessions, so at least
**16 more distinct prior sessions** are required even at the best-covered
minute. A five-minute row is derived from five one-minute rows, not an
independent provider series. The source receipt says the session calendar
and exchange feed are unvalidated.

The sealed five-stock report contains ten INOD SEC 8-K event candidates.
Every candidate retains SEC administrative acceptance time but has
`first_publication_at=null`, `provider_historical_available_at=null`, and
`timestamp_usable_as_verified_news=false`. SEC acceptance is not the first
public news release. There is no source-bound provider arrival or independent
first-publication timestamp for an event in this local evidence. None is
substituted with the retrospective retrieval time.

| Mandatory acceptance item | Observed evidence | Gate |
|---|---|---|
| First public news UTC and historical provider arrival | 0/10 verified event candidates | Open |
| Historical available-at for each minute bar | 0/2,126 source rows | Open |
| Same-clock baseline | 4 prior dates at most, 20 required | Open |
| Certified exchange calendar and intraday source | Neither verified | Open |
| 1m/5m as-of reaction and matured hit/miss/false-positive replay | No valid event anchor or provider-time chain | Open |

The offline gate code is `app/scoring_v13_event_gate.py`, with a sealed private
receipt at `E:/M10/.master_tasks_v13_private/event/inod_event_source_gate_v1.json`,
SHA-256 `9a14c05b991698a5b491cebc337734e0aa9904fb4238ed68918863ab8cecc748`.
It checks original response length/SHA, re-parses the complete response,
cross-checks all saved 1m/5m rows, verifies the ten event candidates and
rejects a newly inserted publication time without independent review. Run
`E:/M10/.venv/Scripts/python.exe scripts/scoring_v13_event_audit.py --verify`
from the V13 worktree to reproduce the receipt. Four targeted tests pass.

**Task 16 remains PARTIAL; verified real alerts: 0; S16-EA score: N/A.**
The next acceptance chain needs a primary timestamped release or archived
contemporaneous feed with first-public and provider-arrival evidence, at least
20 prior verified same-clock sessions with each bar's historical available-at,
an authoritative session calendar, and an outcome window. No alarm or
hit-rate is reported from these retrospective bars.
