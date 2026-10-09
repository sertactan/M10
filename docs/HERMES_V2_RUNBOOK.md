# Hermes V2 — Safe local integration runbook

## Current status
Hermes binary installed: **NO**. Cloud deployed: **NO**.
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
SQLite quota is single-machine only. 90s lease and 30s outgoing timeout
must be validated under killed processes and concurrent requests. The gateway
has no production-grade auth identity, OpenTelemetry cost feed,
independent official proof of model account billing settings or enforced
remote non-billable request proof.
The `canonical_evidence_verified` flag is not a cryptographic proof.
Only an explicitly trusted local M10 provenance checker may set it.

## Cloud blocking decision (2026-10-10)
One e2-micro in eligible US region + qualifying standard 30 GB-month disk
are Always Free candidates. Outbound transfer free threshold is narrow;
external VM IPv4 charge (normally $0.005/h after 1 free hour/month) and
Cloud NAT make continuously connected Hermes non-guaranteed free.
Do not deploy or enable billing without independent verified safeguards
that *actually prevent charges*. Budget alerts do not enforce a hard cap.
