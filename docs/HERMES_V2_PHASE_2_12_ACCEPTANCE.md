# Meridyen Autonomous Hermes V2 — 2026-10-10 source-backed acceptance

**Scope:** feature branch `feat/hermes-autonomous-v2-strict-free`, draft PR #150.
**Status meanings:** PASS means actually executed; PARTIAL means limited integration;
BLOCKED means external evidence/security prevents safe completion.

| Phase | Acceptance as of this development turn | Status |
|---|---|---|
| 0 — Protect M10 | new origin/main Phase25j reconciled, original untracked files untouched; canonical formulas unchanged | PASS |
| 1 — Strict free | official prices and conditional quotas researched; owner account/payment status not accessible, no paid calls | PARTIAL |
| 2 — Hermes install | user's native Hermes 0.21.5+5295 pinned by observed SHA 234badf4; isolated HERMES_HOME runtime staged; source launcher publication intermittently warns | PARTIAL |
| 3 — FREE LLM | local SQLite one-in-flight, cap preflight, secret checks, no paid fallback; no real verified free account | PARTIAL |
| 4 — Six roles | Hermes lists six native project skills as enabled; A1–A6 deterministic local queue executed with real audit scripts, idempotent handoffs | PARTIAL — no real LLM delegation |
| 5 — Cloud | no creation/deployment, zero-cost not guaranteed due public IPv4, egress, disk and IPv6 connectivity | BLOCKED |
| 6 — SEC/Massive/PIT | Phase25j source-only six issuer references and 127 non-P1 candidates triaged; historical share-class mapping and adjusted bars not certified | PARTIAL |
| 7 — Scanner/S16 | source-only scanning pipeline provides evidence counts; formulas unchanged; canonical scores not generated | PARTIAL |
| 8 — S16-EA/Telegram | timestamped catalysts absent -> INCONCLUSIVE; Telegram outbound disabled by default, chat allowlist + mocked transport tested | PARTIAL |
| 9 — Risk/paper | A5 actual Phase25i gate; deterministic fee/slippage/stop/quantity preview is **synthetic scenario only**; no broker calls | PARTIAL |
| 10 — WF9/Learning V3 | A6 real read-only gate reports 9 blockers; no true WF or real training performed | BLOCKED |
| 11 — ChatGPT Private Plugin | localhost authenticated MCP JSON-RPC tools/list/call tested; public TLS/tunnel + ChatGPT actual connection absent | PARTIAL |
| 12 — CI/acceptance | focused pytest and offline real source audit run; full historical and cloud live acceptance not certified | PARTIAL |

## 2026-10-10 continuation — independently confirmed changes

The feature branch integrated `origin/main` Phase25k and Phase25Q without
altering the frozen formulas, private production database, or user untracked
files. Real local Phase25k produced a **133-candidate canonical acceptance
ledger with zero canonical acceptances**.

The **pre-existing** Phase25Q immutable versioned staging repository was
verified *read-only* using its manifest and SQLite `PRAGMA quick_check`
and row-level counts:

| Phase25Q metric | Actual |
|---|---:|
| Historical month-end snapshot dates | 21 |
| Monthly source membership rows | 128,088 |
| Source vendor daily price rows | 2,110,622 |
| Candidate acceptance-gate rows | 133 |
| Canonical PIT identities accepted | 0 |
| Independently verified adjusted-price selections | 0 |
| True WF9 runs | 0 |
| True Learning V3 trainings | 0 |

The source snapshots were retrieved retrospectively in 2026 and SimFin vendor
adjusted prices may embed future corporate action knowledge. These new,
real research-source counts do **not** remove the Phase25i nine acceptance
blockers or establish survivorship-free performance.

### Windows TCP reset resolved and tested

The original HTTP test intermittently reported WinError 10054 while
receiving unauthenticated POST replies. Instrumentation showed that the
server had accepted the socket, entered `do_POST`, and emitted its
`401 Unauthorized` response **without a Python handler exception**.
The handler previously returned before consuming the small POST body;
on Windows closing a socket with pending received bytes can send TCP RST
and obscure the HTTP 401 reply. The fix consumes *at most 16,384 declared
bytes* for unauthorized requests before closing; no unauthenticated data
is parsed, persisted or logged. Real localhost HTTP tests now cover 60
alternating authorized/unauthorized POSTs, `initialize`, `tools/list`,
`tools/call`, persistent tasks and negative authorization, using temporary
SQLite only and no source-archive dependency. This is still a local JSON-RPC
adapter, NOT evidence of live ChatGPT Plugin remote connectivity.

### Native Hermes gateway and paused no-agent cron

Isolated `HERMES_HOME` was used with LLM and Telegram keys disabled.
The installed Hermes v0.21.5+5295.g234badf gateway was started in
foreground; native `gateway status` reported a live PID and `cron status`
reported an active ticker heartbeat. Listener inspection found loopback
`127.0.0.1`. The private `6e92e18ee724` no-agent job was
temporarily resumed, explicitly triggered, **reported "Ran now: succeeded"**
and was recorded in cron run history. It was then **paused again**, and
the foreground gateway was stopped. This proves an actual Hermes
deterministic scheduler execution; it does NOT prove LLM agent delegation,
24/7 service, or bot delivery. Native source launcher update still
emits a warning; no in-place global upgrade was attempted.

### Score and free-usage hardening

External JSON flags cannot create S16-E or S16-C values. Both numeric
scores now require separate trusted local deterministic formula call-site
approval, finite values in [0,100] and validated source/provenance fields.
Until M10 local scoring adapters produce real proof, the response has
`s16_e_status=INCONCLUSIVE`, `s16_c_status=INCONCLUSIVE` and empty
score fields. Sample inputs in unit tests are not live prices.
OpenRouter Free Plan local policies are additionally capped at no more
than 50 requests/day and 20 requests/minute, even if an operator writes
an accidentally larger number. These guards do NOT guarantee provider
billing status, so live inference remains disabled.

## Live vs simulated

**Real-local:** official Hermes executable version check; six Hermes skill registrations
in isolated profile; Python M10 Phase25j source report and Phase25i PIT gate;
native Hermes paused no-agent cron entry; persistent SQLite A1→A2/A3/A4/A5/A6
handoffs; local authenticated MCP HTTP roundtrip.

**Synthetic/offline:** gateway model calls with injected mock transport; Telegram
delivery with injected mock; paper position preview with operator test values;
test SQLite jobs and mock news/financial inputs.

**NOT DONE:** Gemini/OpenRouter real model call (account-based zero spend unverified);
Telegram Bot API live send or receiving commands; authenticated ChatGPT remote
Plugin connection; real distributed/cloud Hermes workers; PIT canonical pricing
and independent historical identity; real WF9 OOS metrics; Learning V3 training;
broker connection or production orders.

## Observed Phase25j

- Six P1 SEC issuer-CIK official filing references: DOYU, HUYA, IRS, SITC, TDG, ZIM.
- Remaining 127 non-P1 distinct candidates (88 P2 plus 39 P3), 167 source-only
  price anomaly records; 182 total source event observations counting 15 P1.
- Historical SimFinId-to-CIK share-class identity certified: zero.
- Canonical backtest eligible among this source review set: zero.
- Phase25j generates private local JSON/CSV, not production DB rows or a
  marketwide list. Public filing evidence is insufficient to certify historical
  split/spinoff/ADR/price adjustment paths.

## Observed Phase25i

`FULL_CHAIN_REAL_DATA_BLOCKED_NOT_TRAINED` due to nine evidence deficiencies:
21/21 canonical month-end memberships, backtest-adjusted selection, corporate
actions, historical issuer share-class CIK, delisting terminal returns,
complete WF5/WF6, mature learning outcomes and independent PIT chain.
No independent whole-market recall or 10X predictive success follows.

## Strict FREE infrastructure ruling

As of 2026-10-10 official sources:
- GCP Always Free eligible e2-micro only us-west1, us-central1, us-east1,
  eligible monthly hours, 30 GB-months standard persistent disk and conditional
  1 GB outbound North America traffic — https://docs.cloud.google.com/free/docs/free-cloud-features
- Standard VM external IPv4 normally $0.005/h, first one hour/month free;
  VM external IPv6 address not charged but network fees/provider IPv4-only
  dependencies, firewall, storage snapshots and other SKUs are not certified —
  https://cloud.google.com/vpc/network-pricing
- Gemini published Free Tier models include gemini-2.5-flash,
  gemini-2.5-flash-lite and gemini-3.7-flash at this date;
  **account-specific AI Studio RPM/TPM/RPD and billing status unknown** —
  https://ai.google.dev/gemini-api/docs/pricing and
  https://ai.google.dev/gemini-api/docs/rate-limits
- OpenRouter Free plan shows 50 requests/day, typical 20 requests/minute;
  no paid-credit uplift allowed; specific `:free` IDs require live validation —
  https://openrouter.ai/pricing/

**CLOUD DEPLOYMENT = BLOCKED.** No billing enabled, no VM/IP/NAT created.

## Repeatable tests and safe operator commands

```powershell
cd E:\M10
$env:PYTHONPATH="E:\M10\data\runtime\hermes_v2\testdeps"
& .\.venv\Scripts\python.exe -m pytest -q tests/test_hermes_*.py
& .\.venv\Scripts\python.exe -m scripts.hermes_team_tasks --db data/runtime/hermes_v2/tasks.sqlite3 enqueue strategy
& .\.venv\Scripts\python.exe -m scripts.hermes_team_tasks --db data/runtime/hermes_v2/tasks.sqlite3 tick
```

Hermes native `cron --no-agent` local script registered in isolated profile
as job `6e92e18ee724`, **paused**. No Hermes scheduler gateway is running;
must not call the job continuously operational until the gateway runs under a
verified local-only configuration. Cron delivery target is local, not Telegram.
Secrets remain outside Git and remote cloud deployment is not authorized.


## 2026-10-10 GitHub-only official Hermes continuation

- Last Windows machine check from this conversation was **unavailable**:
  Chat On Steroids Core and Desktop both returned
  `Tunnel-client has not been seen for 300 seconds`. No local
  uncommitted changes, Windows runtime, original archives, or
  user-specific free model quotas were accessible in this turn.
- Added the Hermes-specific project context `.hermes.md`,
  updated the A1 skill for one-at-a-time official `delegate_task`,
  and created the inactive
  `config/hermes_native_profile.safe.example.yaml`. A native
  profile is **not** an independently running LLM team and no
  actual delegation occurred here.
- Added `tests/test_hermes_native_profile.py`: checks native-only
  toolsets, one child, project-root cwd, no embedded model/keys,
  and all six existing `SKILL.md` files. CI checks the repo
  without Windows data, market calls, or paid provider keys.
- The existing Hermes native no-agent cron was previously observed
  to complete once and was re-paused. That remains earlier evidence;
  it was **not** resumed in this turn.
- All 133 researched Phase25Q candidates remain unapproved for
  canonical PIT, despite 21 retrospective source months,
  128,088 membership observations and 2,110,622 source price rows.
  No live price or actual Learning V3 / WF9 performance is asserted.
- Real user-account Free Tier, Telegram token, remote MCP TLS,
  Google Cloud VM/IP/network hard cost guard and direct Windows
  CLI access are the current outside dependencies.
- Prior code/CI successes should not be misreported as
  a real six-agent free LLM team or deployed Hermes service.


## 2026-10-10 — Phase25M/R/S upstream merge and source-only adapter

GitHub main `f2a755b` was merged into the feature branch by
[merge commit 74dcb41](https://github.com/sertactan/M10/commit/74dcb414d3224bd5ff2324f80170e454e89e2e9b).
Nine upstream additions only (Phase25M/R/S docs, scripts and tests); no
canonical S15.3/S16/S16-EA formulas or user runtime files changed.

Additional **pre-existing source evidence** brought into scope:
- Phase25M: 6 official issuer distribution references for CRCT, IEP and EC,
  matching 13/167 anomalous source intervals. 154 other warnings remain
  outside this issuer review. No ex-date/ADS/FX/elective-unit or adjustment
  factor certification.
- Phase25R: 21 retrospective monthly listings include 464 conflicting
  month+exchange+ticker historical issuer rows and 21 identical duplicate
  rows; 30 conflicting ticker strings, including 7 in the strong cohort:
  B, CWBC, FUN, STRR, TEL, TTE and VIVO. All seven need identity
  quarantine; 3,557 previously strong candidates are not PIT certified.
  Phase25R reconciled 1,557,903 qualified price observations using
  the original source reports. The new Hermes adapter does **not**
  recalculate them.
- Phase25S: official SEC documents support SITC Aug 16 2024 1-for-4
  reverse split and Oct 1 2024 distribution of two CURB shares per
  SITC common share on the Sep 23 record date. Official issuer event
  evidence is **not** sufficient for complete SimFin adjustment,
  historical security-class, or total shareholder-return certification.
  The earlier Windows report explicitly warned that a real Phase25S
  local execution had not been observed.

Added `core/hermes_team/phase25_source_evidence.py`, which only reads
the *already existing* private Phase25M/R/S JSON outputs, checks exact
schemas and fail-closed certification flags, checks Phase25R's
quarantine-list length and 7 tickers, records a SHA256 digest of the
report bytes, and emits compact status without private raw source
rows. Absence or conflict => `INCONCLUSIVE`. It is a verification
of report **consistency**, not independent validation of all SEC
facts nor proof of timely historical availability.

`core/hermes_team/evidence_workflows.py` attaches these evidence
snapshots to existing Phase25i/25j Python-only tasks (not LLM
delegation). `tests/test_hermes_phase25_source_evidence.py` and
the additional source-workflow integration test use temporary
fixtures; no Windows archive, SEC network call, premium data feed,
broker, or production DB mutation.

**Runtime status this turn:** Windows Chat On Steroids tunnel remained
offline, so a real Windows Phase25R/25M/25S file read and native
Hermes `delegate_task` could not be performed. Model and account
billing controls remain unverified; live inference stays disabled.
No additional PIT selection has passed canonical acceptance,
and no actual WF9/Learning V3 score or training occurred.
