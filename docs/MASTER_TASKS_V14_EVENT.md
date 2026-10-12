# V14 Task 16 — scheduled-session audit

The original, sealed INOD source still contains 2,126 one-minute bars over
5–9 October 2026 and 218 **derived** five-minute bars. The latter are not an
independent five-minute feed. The original response SHA-256 remains
`6f3746effd4dad60c5944a65b7c6f989757e61f14cd5772475cefd176bd400f1`.
The sealed ten SEC 8-K candidates still have no independently established
first-public news time or historical provider arrival time.

The [Nasdaq Trader 2026 U.S. equity holiday schedule](https://www.nasdaqtrader.com/Trader.aspx?id=Calendar)
lists 5–9 October as scheduled open dates. For the 9 October evaluation date,
the preceding 20 scheduled dates run from 11 September to 8 October. The
original market source covers only 5–8 October, four of those 20 dates. The
other **16 scheduled dates have no sealed minute bars**. The calendar lookup
establishes a published schedule; its raw HTML was not sealed locally, and it
does not certify individual INOD trading, halts, bar arrival times, or an
exchange-sourced OHLCV feed.

| Acceptance evidence | V14 finding | Gate |
|---|---|---|
| Nasdaq published scheduled dates | 20 prior dates enumerated; four dates overlap the five-day source | Calendar research only |
| Historical 1m bars at each comparison clock | At most four prior distinct dates | Open: 20 required |
| Independent 5m source | Only 218 rows derived from 1m | Open |
| Bar-level historical available-at | None in the original source | Open |
| First-public news and provider arrival | 0/10 SEC candidates verified | Open |
| As-of reaction and outcome replay | No valid event and provider-time chain | Open |

The V14 private calendar receipt is
`E:/M10/.master_tasks_v14_private/event/inod_nasdaq_calendar_gate_v1.json`,
SHA-256 `e7a3568b3c4396f05d354f42aa92fa10d3e9b01fc1c150ba5009e112ee8f8b48`.
`scripts/scoring_v14_event_audit.py --verify` replays the original response,
V13 source gate, published-calendar date rules and V14 receipt; four targeted
V14 tests cover the holiday, exact prior-date window, fail-closed state and
private replay. A request for additional historical 5m bars received HTTP 429;
it was not retried, and no new bars were accepted.

**Task 16 remains PARTIAL. `16.bars` and `16.events` remain OPEN. Verified
alarms: 0. S16-EA score: N/A.**
