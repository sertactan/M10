# Hermes V2 — native setup checklist (official Hermes, not a replacement agent)

Status 2026-10-10: this checklist and `.hermes.md` are committed in PR #150.
The Windows tunnel is **currently offline**; steps below were not executed
in this update. Earlier turns confirmed the installed official Hermes CLI
v0.21.5+5295.g234badf, six project skills, a working private-profile
gateway/cron smoke test, and a paused cron job `6e92e18ee724`.

## 1. Preserve the real local installation

In PowerShell, once the user's computer tunnel is connected:

```powershell
Set-Location E:\M10
git status --short --branch
git log -1 --oneline
$env:HERMES_HOME = 'E:\M10\data\runtime\hermes_v2\hermes_profile'
& "$env:LOCALAPPDATA\hermes\bin\hermes.exe" --version
& "$env:LOCALAPPDATA\hermes\bin\hermes.exe" doctor
& "$env:LOCALAPPDATA\hermes\bin\hermes.exe" skills list
& "$env:LOCALAPPDATA\hermes\bin\hermes.exe" cron list
```

Do not run the upstream remote installer or `hermes update` automatically.
Inspect any `source launcher publication failed` warning before a pinned
update. Don't alter the personal Hermes profile, the `main` branch or private
data stores.

Hermes' official project-context discovery gives `.hermes.md` priority.
Run native Hermes from `E:\M10` (or set its approved `terminal.cwd`);
background cron sessions otherwise lack the repo's project context.

## 2. Use built-in skills and delegate_task

Six skills are already in `.agents/skills`. In the **isolated** profile,
review `config.yaml` before editing it. Only after model/free billing evidence
is verified, set the supported official Hermes delegation limits:

```yaml
delegation:
  max_concurrent_children: 1
  max_spawn_depth: 1
  orchestrator_enabled: false
```

These settings limit child-agent concurrency; they are NOT a universal
model-call budget or external provider billing block. Every provider request
must still go through the separately authenticated local one-in-flight
`core/hermes_team/gateway.py` and persistent `QuotaGuard` ledger.
Do not configure Hermes to fall back to Nous, OpenAI, OpenRouter paid,
Gemini paid, or an automatically selected model. If Hermes cannot be
restricted to one private gateway provider, **keep all LLM work disabled**.

Native delegation pattern *after* successful zero-cost validation:

- A1 controls the task; use `delegate_task` with a concrete `goal` and
  standalone `context` for one child at a time.
- A2 receives only read-only discovery scope and source timestamps.
- A3 receives A2's evidence, filing accession/available-at and permitted
  local paths. Wait for A3 completion before A4.
- A4 reviews timestamped verified catalysts and may return INCONCLUSIVE.
- A5 independently vetoes any unsupported risk or paper signal.
- A6 independently validates the PIT/WF9/Learning V3 evidence and may block.
- Leaf children must not be authorized to change tools, route paid models,
  edit canonical formulas, send messages or create schedules.

A `delegate_task` child inherits the parent's toolset. Hermes project
skills and approval text are **not** an operating-system security sandbox.
Restrict terminal and file capabilities before trusting remote source content.

## 3. One shared, pinned free model before six logical roles

No model is currently active for the six roles. Candidate *published* free
model IDs (not proof of account entitlement): `gemini-3.8-flash`,
`gemini-2.5-flash`, and `gemini-2.5-flash-lite`. Google currently restricts access to some legacy
2.5 models for new projects; enumerate the actual model list on the
**specific** AI Studio project and verify Free Tier, RPM/TPM/RPD and
billing disabled/hard blocked. OpenRouter `:free` IDs are candidates,
not a billing guarantee. Never copy secrets into Git or chat.

The profile should route all six logical roles to **one verified pinned
model behind the same local policy gateway**, not deploy six running LLM
servers. Confirm parallel child requests cannot bypass the global ledger.
If the account cannot technically block payable requests, leave the policy
`enabled=false` and run Python-only roles.

## 4. Read the M10 code; reuse the finance engine

Hermes in `E:\M10` reads already checked-out Git files using its native
terminal/file tools. Do not copy M10 into another custom Hermes app.
Allowed initial commands: `git status --short --branch`, `git log -1`,
and read-only source inspection. No push/merge without approval.

For real deterministic research, prefer existing M10 scripts and native
Python, not generated S15.3/S16 formulas:

```powershell
& .\.venv\Scripts\python.exe -m scripts.phase25i_real_market_gate_matrix
& .\.venv\Scripts\python.exe -m scripts.phase25j_p1_sec_issuer_and_p2p3_source_triage
```

`core/hermes_team/m10_bridge.py` requires a separate verified PIT provenance
callback before S16-C. `scripts.hermes_pit_stage_audit` validates only the
private Phase25Q research staging, **not canonical PIT**. No 252-session
labels/backtest may be claimed without actual date-valid evidence.

## 5. Native cron first, Telegram and Google Cloud last

Hermes' native cron supports `--no-agent` scripts with zero model calls.
The isolated profile job `6e92e18ee724` was successfully manually
triggered in a previous turn and deliberately re-paused; do not resume
it for unattended work until the path/permissions are reviewed.

Next, configure a separate Telegram Bot API token and exact allowed chat
in private environment variables. First test identity and a harmless
`/status` message; never send trading orders. The local MCP adapter
must stay bound to loopback; connecting it to ChatGPT requires verified,
authenticated TLS routing and actual `tools/list` handshake.

Only after local native Hermes, zero-billable LLM model, Telegram and MCP
have real evidence: review Google Cloud Always Free e2-micro, disk, IPv4,
IPv6, NAT, region, egress and API routing. Without a true no-charge
enforcement path **do not create or start cloud resources**.

Official references:
- https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation
- https://hermes-agent.nousresearch.com/docs/user-guide/features/cron
- https://hermes-agent.nousresearch.com/docs/user-guide/features/tools
- https://hermes-agent.nousresearch.com/docs/user-guide/git-worktrees/
- https://ai.google.dev/gemini-api/docs/pricing
- https://docs.cloud.google.com/free/docs/free-cloud-features
