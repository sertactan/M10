# Tasks 13 / 15 / 16 — offline Estimated proposal and provider evidence

Reviewed 2026-10-11. Base: `c071076`. This adds an experiment to the Phase28
`PHASE28_S16_E_ESTIMATED_DESIGN_DRAFT.md` proposal; it does not approve, replace,
or activate an S16 model. Existing S16-C and S16-EA formulas are unchanged.

## 15. S16-E engineering sub-deliverable

**Prototype/design: VERIFIED_DONE. Activation: PENDING_APPROVAL. Calibration:
DATA_MISSING. Complete task 15: PARTIAL. Genuine ticker scores produced: 0.**

`app/scoring_estimated_draft.py` is a pure, offline function module. No startup,
UI, model registry, provider, database, network or file writes are connected.
`experiment(...)` requires `acknowledge_unapproved_experiment=True`; its output
always has `runtime_enabled=False`, `canonical=False`, `confidence=UNCALIBRATED`
and `activation_status=PENDING_APPROVAL`. The flag permits an offline experiment,
and is not owner formula approval. Normal calls return no numeric result.

Version: **S16-E-EXPERIMENT-DRAFT-0.2**. Proposed horizon: **1–5 trading sessions**.
Every numerical weight, threshold and penalty below is a NEW uncalibrated design
proposal. None is a recovered frozen normalization. Before activation, the owner
must approve this complete version and its validation evidence explicitly.

### Proposed normalization and weights

For each favorable factor, `N(x)=100*clamp((x-L)/(U-L),0,1)`; reverse factors use
`100-N(x)`. Fractions are decimal fractions, not percentage points. Inputs must
be independently calculated with the following semantics; this module validates
their envelope, not the correctness of the underlying source bytes/calculation.

| Raw input / definition | L | U | Weight | Freshness from period end |
|---|---:|---:|---:|---:|
| Close-to-close return over 5 exchange trading sessions | -0.10 | 0.20 | 20% | 96 h |
| Most recent complete session volume / previous 20 complete-session mean volume | 0.5 | 3.0 | 20% | 96 h |
| Mean of close × volume over 20 completed sessions, USD | 1m | 20m | 15% | 96 h |
| Independently reported public float shares (reverse; never listed shares) | 5m | 200m | 10% | 100 d |
| Hours since independently evidenced first public catalyst release (reverse) | 0 | 120 | 15% | 120 h |
| TTM (operating cash flow minus positive capex outflow) / same-period revenue | -0.10 | 0.30 | 10% | 180 d |
| A preselected fixed benchmark close return over 20 completed sessions | -0.10 | 0.10 | 10% | 96 h |

Benchmark selection must be fixed before replay, and recorded with input source
provenance. Regime choice is not optimized per outcome. All lookbacks need a
verified exchange session calendar and consistent corporate-action treatment.
The float factor is only a supply proposal; it is not a short-interest proxy.

Each risk uses `15*clamp((x-L)/(U-L),0,1)` points:

| Required raw risk | L | U | Maximum penalty | Freshness |
|---|---:|---:|---:|---:|
| Period-matched shares-outstanding year-over-year dilution fraction | 0.02 | 0.20 | 15 | 180 d |
| Actual contemporaneous `(ask-bid)/mid*10000`, basis points | 20 | 200 | 15 | 1 h |
| Sample standard deviation of 20 completed-session log returns × sqrt(252) | 0.40 | 1.20 | 15 | 96 h |

`experimental_score=clamp(sum(weight*N)-sum(penalties),0,100)`.
There are **10/10 hard required fields**, including every risk. Missing or invalid
inputs yield **NO_SCORE**, never zero-fill, default 50 or weight redistribution.
Raw domains and maximum ages are versioned in `FACTORS` / `RISKS` in the module.
Boolean values, nonfinite numbers, wrong units, malformed hashes, unknown fields,
unconfirmed identity and an unavailable source reference block scoring.

Every input carries timezone-aware `period_end`, `available_at`, `observed_at`.
The required order is `period_end <= available_at <= observed_at <= decision`.
Retrospectively observed records cannot be replayed as contemporaneous inputs.
`availability_basis` must be `PROVIDER_CAPTURE_LOG`; `SEC_ACCEPTED` is rejected.
The catalyst age must independently agree with its event timestamp. These checks
validate supplied metadata, not its authenticity. A source hash string alone is
not proof that underlying bytes, identity or publication claims are correct.

### Replay / calibration boundary

`evaluate_frozen_replay(...)` takes predeclared thresholds and separate matured
outcomes. Future label availability and future input observations are excluded;
duplicate case IDs are rejected. It returns TP/FP/TN/FN, precision, false-positive
rate and false-alert fraction, with undefined denominators left null. It never
selects thresholds, tunes weights or generates numerical confidence.

**13 Python 3.11 unit tests passed** with synthetic fixtures, including independent
arithmetic, required-input removal, future timestamps, invalid data, source/time
checks, deterministic ordering and replay contamination. These are software
checks, not performance, calibration or genuine ticker-score evidence.

Before calibration: freeze the point-in-time cohort and split dates; verify
provider capture logs, delisted securities, identity and corporate actions;
freeze the 1–5-session exit calendar and outcome thresholds; purge overlapping
outcomes at train/validation/test boundaries; compare a preregistered baseline
and report per-regime counts, Precision@K, false alerts, drawdown and costs. Keep
a final untouched holdout. The harness does not certify cohort representativeness,
outcome authenticity, valid session horizon or economic accuracy. Those remain
**DATA_MISSING**, so no success rate or numeric confidence is reported.

## 13. SEC official access and timing

Presence-only configuration inspection found `SEC_USER_AGENT` and
`ALPHAVANTAGE_API_KEY` configured in the original local `.env`; values were not
printed, copied into the worktree or committed. SEC contact has a non-placeholder
email-shaped value; actual ownership/deliverability has not been verified.
Process/User environment variables were absent, as was a worktree `.env`.
Thus the file's existence does not prove a launched provider receives it.
`app/data_bootstrap.py::_sec_user_agent` reads the environment and otherwise uses
a repository URL without a contact email. The existing
`scripts/phase14_sec_submissions_collect.py` requires a non-placeholder contact
and uses a 0.5-second minimum interval. No identity was invented or changed.

The last recorded actual access result remains the Phase28 **HTTP 403**. This
subtask fetched official documentation only, with no repeat Companyfacts,
Submissions, prices or financial download. It does not claim a new endpoint
success or a fresh 403 result.

Permitted path: supply the already authorized real contact to the existing
collector, coordinate all concurrent SEC jobs under the shared request limit,
keep bounded cached requests, and stop on denial. The SEC permits declared
scripted access with an aggregate maximum of 10 requests/second. For continuing
Access Denied, the official support path asks for the error and IP; no support
message was sent. [SEC developer guidance](https://www.sec.gov/about/developer-resources),
[SEC FAQ](https://www.sec.gov/about/webmaster-frequently-asked-questions).

Companyfacts and Submissions are official keyless JSON APIs. SEC bulk archives
are nightly, so they do not independently establish historical first availability.
[SEC API documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces).
Keep SEC acceptance, SEC dissemination, provider capture, local retrieval and
any derived availability dates distinct. SEC says acceptance-to-web delays vary;
its typical latency is not a timestamp for an individual filing. The archived
Phase27/28 rows with null acceptance and derived `available_at` remain Research.
No canonical admission follows from improved contact configuration.

**Status: PARTIAL / historical timing DATA_MISSING.** A compliant contact does
not by itself fix an IP denial or prove archived timestamps.

## 16. 1m / 5m provider feasibility (official documentation)

| Provider/path | Documented access | Current local finding | Consequence |
|---|---|---|---|
| Alpaca stock bars / IEX | Free live IEX; bars support 1Min / 5Min | APCA key/secret absent from inspected process/user environment and main `.env`; no account created | Potential free source, not currently integrated or downloaded |
| Alpaca historical SIP | FAQ permits historical queries with end at least 15 minutes old without subscription | Credentials/entitlement and actual response not verified | Potential retrospective research; not proof of historic provider arrival |
| Alpha Vantage intraday | Official stock intraday page labels endpoint Premium, including historical/15-minute-delayed access | Local key present; paid entitlement not used or assumed | Not an available free intraday solution under zero-spend policy |
| SEC RSS/Submissions / issuer release | Filing/event source, not price bars | Prior 403 and missing first-public/time evidence remain | Cannot substitute for 1m/5m prices or exact news arrival |

Alpaca references: [market-data FAQ](https://docs.alpaca.markets/us/docs/market-data-faq),
[stock-bar API](https://docs.alpaca.markets/us/reference/stockbars).
Alpha Vantage: [official intraday documentation](https://www.alphavantage.co/documentation/#intraday).
No provider marketing claim is counted as a delivered evidence record.

IEX covers a single exchange. Its volume is not consolidated US volume; feed
identity must be preserved and cannot silently replace a frozen whole-market
baseline. A later historical SIP retrieval proves present retrievability, not
past system knowledge. Bars must be available only after the complete bar ends,
with original feed, UTC/source timestamps and exchange-local session mapping
(America/New_York daylight saving and real holiday/half-day calendar). Preserve
premarket separately; absent premarket bars are not a proven zero. News-at-Open
requires primary first-public time, and Zero-PM Breakout requires the actual
same-clock history and premarket coverage. None was fabricated here.

**Status: DATA_MISSING / no genuine alert produced.** No subscriptions, financial
or price redownloads, credential creation, access bypass or runtime activation.
Canonical **0/0**; WF9 **BLOCKED**; Learning V3 **NOT_TRAINED**.


## Parent integration update (2026-10-11 JST)

The feasibility subtask above preceded two bounded live checks. The parent used
the existing configured SEC contact for one official INOD Submissions request:
HTTP200, response SHA070461656ae36691ad952bd53e529dd48fbb74b8f7191637d3c6bb79e27910f3.
Two used accessions now have separately matched SEC acceptance times; historical
provider availability and first-public dissemination remain missing. No repeat
Companyfacts download occurred. The earlier403 is historical, not the latest
Submissions result.

One new Yahoo-compatible research request delivered2126 valid1m bars and218
complete derived5m groups. This unofficial current-retrievability probe is not
exchange-certified or a promise of continued free access. No provider credentials
or subscriptions were created. Same-clock baseline/calendar and first-public news
remain unverified; no S16-EA alert or performance result was produced. Detailed
receipts and scope are in SCORING_TASKS_09_18_STATUS.md.
