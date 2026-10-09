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

## Cloud blocking decision (2026-10-10)
One e2-micro in eligible US region + qualifying standard 30 GB-month disk
are Always Free candidates. Outbound transfer free threshold is narrow;
external VM IPv4 charge (normally $0.005/h after 1 free hour/month) and
Cloud NAT make continuously connected Hermes non-guaranteed free.
Do not deploy or enable billing without independent verified safeguards
that *actually prevent charges*. Budget alerts do not enforce a hard cap.
