# Hermes V2 — Safe local integration runbook

## Current status
Hermes binary installed: **YES** — Windows v0.21.5+5295.g234badf,
git SHA 234badf4012af380d23c91eae55d045a69c69ffb, not upgraded.
Official v0.21.6 released 2026-10-08 (818c13be1dc4fd28987e1e881a9408224afd4535).
Cloud deployed: **NO**.
Private Plugin connected: **NO**. Telegram connected: **NO**.
True PIT 10–15 year walk-forward validated: **NO**.
No provider credentials, pricing claims or user billing settings were invented.

## Developer smoke / tests
```powershell
cd E:\M10
python -m compileall -q core/hermes_team scripts/hermes_team_gateway.py
python -m pytest tests/test_hermes_team.py -q
```
Test dependencies may not be installed. This integration creates no broker orders,
no cloud resources and no provider calls unless operator manually enables it.

## Policy activation (future operator-only)
Copy `config/hermes_team.example.json` to a file *outside Git*.
Verify actual provider model ID, non-billable API account, fresh pricing and
rate limits on official dashboard. Fill the exact verified ID, expiration,
daily/minute caps; only then set enabled true. Store the protected
`MERIDYEN_HERMES_GATEWAY_KEY` (>=32 chars) and the one approved provider
API key in private secret store; never in source.

Do not start the service just to test unverified models. On a machine with
private verified credentials, a **manual** start command is:
```powershell
python -m scripts.hermes_team_gateway --policy D:\Private\hermes-policy.json --ledger D:\Private\hermes-quota.sqlite3
```
Gateway only listens at `127.0.0.1:8765`; integrate through private local
OpenAI-compatible endpoint, exact pinned model, Authorization Bearer
gateway secret. Set Hermes native fallbacks/direct provider routes to OFF.
Hermes tool execution, workflow credentials, web search and Telegram
require separate explicit capability allowlists. This is not yet a complete
Hermes config or live, independent security boundary.

## Hermes upstream installation — not executed
Official docs: https://hermes-agent.nousresearch.com/docs/getting-started/quickstart/
Use audited, pinned upstream release, then `hermes setup`,
`hermes model`, `hermes doctor`; enable gateway only after local chat
and zero-billing guard verification. On the tiny VM skip browser automation.
Never execute an unreviewed remote install script in the running M10 checkout.

## Network and security limitations
Loopback only does not protect against other untrusted local processes.
SQLite quota is single-machine only. Active unfinished leases are NOT
automatically released on timeout; inspect crashes manually. The gateway
has no production-grade auth identity, OpenTelemetry cost feed,
independent official proof of model account billing settings or enforced
remote non-billable request proof.
The `canonical_evidence_verified` flag is not a cryptographic proof.
Only an explicitly trusted local M10 provenance checker may set it.
The S16 bridge requires an independent verifier callback; none is yet
wired to the actual production PIT source. JSON flags alone cannot attest
canonical results.

## Hermes native roles and recoverable queue

Six skills are defined as project-scoped `.agents/skills/meridyen-*/SKILL.md`
instructions. Native Hermes CLI supports `skills trust [path]`, but no
global trust or unattended execution was enabled. Persistent local-only
SQLite queue: `python -m scripts.hermes_team_tasks --db
data/runtime/hermes_v2/tasks.sqlite3 enqueue scan`, then change final
argument to `tick` to execute one no-network/no-LLM fail-closed status
assessment, or `status JOB_ID` to inspect. Interrupted RUNNING tasks
require review; no auto-repeat. This queue is not yet the full M10 scanner.
Native Hermes `cron create --no-agent --script` and `cron runs` can be
used once manually approved; no job was scheduled in the user's profile.

Official Hermes release pinning, actual user-owned LLM quota and
nonbillable account guard, live Telegram/plugin transport, complete
144-month PIT, WF9, and real Learning V3 performance remain unverified.
IPv6-only GCP may avoid IPv4 address charge but does not establish
zero total spend or provider connectivity; cloud remains blocked.

## 2026-10-10 continuation acceptance evidence

- Feature branch reconciled with upstream main through Phase25i; main and
  local untracked user files remain untouched.
- Installed Hermes v0.21.5 verified. A separate private
  `HERMES_HOME=data/runtime/hermes_v2/hermes_profile` was selected;
  initial dependency preparation started but complete native role/CLI
  invocation has **not** been demonstrated as successful.
- The A6 `learning` queue task now invokes the actual existing
  `scripts.phase25i_real_market_gate_matrix` read-only M10 audit. Tested
  on local Windows: `FULL_CHAIN_REAL_DATA_BLOCKED_NOT_TRAINED`,
  nine reported blockers, `walk_forward_executed=false` and
  `Learning_V3_executed=false`. This is NOT model training.
- Offline safety smoke, compilation and actual SQLite task round-trip
  passed. Full pytest regression, real gateway provider calls, actual
  Telegram delivery and authenticated MCP handshake are still pending.
- The isolated Hermes profile must complete installation and pass
  `hermes doctor` before marking native Hermes integration accepted.

## End-to-end deterministic six-role execution and adapters

The updated `core/hermes_team/evidence_workflows.py` orchestrates existing
M10 Phase25i and Phase25j scripts using a bounded subprocess and returns
their own source statuses without inventing S15/S16 scores. SQLite queue
supports single active worker, idempotent A1 specialist handoff, operator
review of interrupted jobs, audit history, secret-containing payload
rejection and explicit blocked results.

Authenticated local MCP (Streamable HTTP JSON mode) is available by manually
running `python -m scripts.hermes_team_mcp --db
data/runtime/hermes_v2/mcp_tasks.sqlite3`, only with a separately stored
32-character-plus `MERIDYEN_LOCAL_MCP_TOKEN`. Binds `127.0.0.1:8876`,
never exposed to public internet. Tools include status, submit, tick, job
inspection and **synthetic-only paper scenario preview**. A real ChatGPT
remote plugin handshake has not been performed. Do not confuse tests of
localhost MCP protocol with the Private Plugin connecting to ChatGPT.

Telegram commands are pure allowlisted `interpret_update` routines.
Outbound delivery is blocked unless SEND_ENABLED=true plus bot token and
exact chat ID are independently configured and opted in. No real send or
webhook was run; transport is mock-tested without any retries.

Hermes native `cron create --no-agent` registered the private profile
`6e92e18ee724` job pointing to the bounded offline Python shim,
every two hours, paused. Gateway scheduler absent; it is not active.
See `docs/HERMES_V2_PHASE_2_12_ACCEPTANCE.md` for actual acceptance status.

## A1-to-specialist execution trace (real local inputs, no LLM)

```powershell
$db = "data/runtime/hermes_v2/tasks.sqlite3"
python -m scripts.hermes_team_tasks --db $db enqueue strategy
python -m scripts.hermes_team_tasks --db $db tick
# Only after A1 finished, replace JOB_ID with the new A1 id:
python -m scripts.hermes_team_tasks --db $db handoff JOB_ID scan
python -m scripts.hermes_team_tasks --db $db handoff JOB_ID fundamental
python -m scripts.hermes_team_tasks --db $db handoff JOB_ID catalyst
python -m scripts.hermes_team_tasks --db $db handoff JOB_ID risk
python -m scripts.hermes_team_tasks --db $db handoff JOB_ID learning
# Invoke tick once for each queued job. An interrupted RUNNING job blocks
# further dispatch until explicit operator review; do NOT auto-retry.
python -m scripts.hermes_team_tasks --db $db review-interrupted STUCK_JOB_ID
```

Source research scripts Phase25j (A2/A3) and Phase25i (A1/A5/A6)
were actually executed. A4 returned INCONCLUSIVE without a current,
timestamp-verified catalyst. An A1-to-A6 chain was persisted locally
with one attempt per specialist, and no network LLM provider or broker
was invoked. A3's official SEC issuer references are not proof of an
entire historical daily share-class identity.

The local MCP endpoint supports authenticated JSON-RPC 2.0 with
`initialize`, `tools/list`, `tools/call`, and `ping`. This is a
**loopback development adapter**. It cannot be added as a production
ChatGPT remotely hosted connector without an authenticated TLS
transport, network routing, plugin authorization and real handshake.

The Free Tier models listed on official Gemini pricing pages are
**candidates only** until the exact AI Studio project has verified model
access and its RPM/TPM/RPD; OpenRouter's `:free` endpoints are account
subject to quota and not an entitlement to bypass 50/day basic cap.
The service is disabled without billing safeguards. An empty private
`.env` is not a real provider configuration.

## Verified 2026-10-10 local Hermes and Phase25Q continuation

- Windows HTTP 10054 root-cause reproduction and bounded fix documented in
  `docs/HERMES_V2_PHASE_2_12_ACCEPTANCE.md`.
- `python -m scripts.hermes_pit_stage_audit --stage-dir
  <the-existing-private-versioned-research-stage>` runs read-only SQLite
  `PRAGMA quick_check`, validates 21 snapshot dates, source row counts,
  133 candidate gate records, and the zero-canonical manifest. The optional
  private stage is discovered conservatively by A1/A2/A3/A5/A6 and its
  verification results are included without reading/writing production DB.
  If more than one version is present, automatic version selection is
  blocked pending operator review.
- Hermes native gateway was **actually started** with an M10-only
  `HERMES_HOME` and without API/messaging credentials, the cron ticker
  heartbeat was observed, and the paused offline job was temporarily
  enabled and explicitly run once. Hermes reported success and a recorded
  execution. The job was paused and the gateway was stopped afterward.
- No paid Gemini/OpenRouter fallback, Cloud Run/VM, broker order, or model
  promotion was enabled. No model scores were synthesized.

- Both estimated S16-E and canonical S16-C now require distinct internal
  trusted formula-derived authorization; external payload fields alone cannot
  inject a score. A verified live price still needs separate actual
  source evidence and timestamp; no real-time price is claimed here.
- OpenRouter free-only local cap ceiling is 50/day, 20/minute, with no
  paid/free auto-routing. The operator must prove live account eligibility
  before enabling the LLM gateway.

## Cloud blocking decision (2026-10-10)
One e2-micro in eligible US region + qualifying standard 30 GB-month disk
are Always Free candidates. Outbound transfer free threshold is narrow;
external VM IPv4 charge (normally $0.005/h after 1 free hour/month) and
Cloud NAT make continuously connected Hermes non-guaranteed free.
Do not deploy or enable billing without independent verified safeguards
that *actually prevent charges*. Budget alerts do not enforce a hard cap.


## Official Hermes-first continuation — inactive profile candidate

The GitHub branch now contains a native Hermes profile template
`config/hermes_native_profile.safe.example.yaml`; it has **not**
been installed in the private M10 `HERMES_HOME` because the
Windows tunnel was offline in this turn.

Use the official `hermes tools` and `hermes config` interfaces to
review tools/config before applying it; do not overwrite an existing
`config.yaml`. There is no configured free LLM or API key.
`delegation.max_concurrent_children: 1` prevents parallel
subagent batches within the profile, but only a verified private
inference gateway and provider billing guard can attempt to ensure
a single system-wide, nonbillable call.

The A1 native `delegate_task` procedure is in
`.agents/skills/meridyen-chief-strategist/SKILL.md`. Skills plus
documented delegation configuration are not proof that an LLM
actually executed the six specialists. The previous Python task
queue is retained only for local deterministic M10 evidence runs,
not extended into a replacement Hermes program.

Static CI test: `python -m pytest -q tests/test_hermes_native_profile.py`
(Python PyYAML available in the current GitHub CI dependency set).
Operator checklist:
`docs/HERMES_NATIVE_EXECUTION_CHECKLIST.md`.

Keep the native cron paused and the gateway stopped by default
until nonbillable account access and all security checks have passed.


## Phase25M/R/S evidence import into official Hermes native skill workflow

Native Hermes A2/A3/A5/A6 skills now refer to the existing
Phase25M/R/S issuer-action and historical identity research
artifacts rather than inventing reports or rerunning the entire
2,110,622-row Phase25Q data pipeline. Hermes' existing terminal
or code-execution tools may inspect the source files when the M10
working directory and read permissions have been explicitly reviewed.

For Python-first evidence-summary callers:
`core.hermes_team.phase25_source_evidence.local_phase25_sources()`
reads the specific existing private report paths under
`%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase25m`,
`phase25r` and `phase25s` in read-only mode. It never writes
private reports or raw prices. If source reports are absent,
corrupt, stale in provenance, symlinked, or have changed schema/
acceptance flags, it reports `INCONCLUSIVE`.

A source-report SHA256 is only an integrity fingerprint for the
bytes actually read; it is **not** a cryptographic certification of
the original SEC disclosure timing, vendor-adjustment method,
split price continuity, terminal delisting returns or complete
point-in-time identity.

Native system-wide LLM cap requires verifying parent plus child
requests through one policy gateway, not just
`delegation.max_concurrent_children: 1`. A real Hermes
model-driven `delegate_task` has not been run in this turn,
because the Windows tunnel and account-level free-API evidence
are unavailable. Do not confuse the deterministic local
A1→A2/A3/A4/A5/A6 SQLite transfers with native Hermes LLM child
execution.


### Phase25L B/FUN issuer transition audit

When Windows returns, use the **existing** official M10 research
`scripts.phase25l_b_fun_official_identity_transitions` with its
previously produced Phase25R file (no download or reimport).
Source-only output lives at
`%LOCALAPPDATA%\S153ResearchTerminal\runtime\phase25l\b_fun_official_historical_identity_transition_evidence.json`.
Hermes' M10 data adapter `core.hermes_team.phase25_source_evidence`
accepts that report only if its B/FUN source fields, 4 official
event references, documented issuer CIKs, $47.50 Barnes
consideration and all fail-closed gate values match.
It returns only compact research metadata, never a canonical price,
training label or brokerage instruction.

Desktop Phase25TU evidence UI code was merged into the feature
branch as part of `main`, but it was **not exercised on Windows**
in this turn; CI source tests are not a desktop click-through test.


### SEC acceptance lower bound — Phase25P

M10's existing `core.research.sec_publication_gate` and
`scripts.phase25p_sec_acceptance_floor` were merged from main.
Do not treat an SEC 10-K/20-F period-end or EDGAR
`Accepted` clock as independently observed market information.
The accepted time is a lower bound; an historical feature is usable
only if genuine public dissemination and vendor feature
`available_at` timestamps exist and the strategy decision
time is later than both.

A3/A5/A6 use the existing `phase25p` private report through
`core.hermes_team.phase25_source_evidence`; source report must
show three accepted-index records and **zero** historically
usable features. A missing report is `INCONCLUSIVE`,
not implicit approval. The upstream Phase25P program is only
a source-evidence research script and does not open premium
feeds or modify operational.db. No Windows execution was
possible while the tunnel was offline.
