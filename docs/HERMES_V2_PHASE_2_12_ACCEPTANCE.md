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
