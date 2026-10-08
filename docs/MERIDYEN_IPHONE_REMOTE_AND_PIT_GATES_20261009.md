# Meridyen iPhone-only cloud verification and noncanonical data boundary

**As-of:** 2026-10-09 Asia/Tokyo.
**Scope:** GitHub + Render cloud actions from iPhone; no Windows runtime, broker, paid feed, silently changed scoring engine, or secret material.

## 2–7: remote MCP and PRIVATE plugin
1. OpenBB owner OAuth source and 7 security regressions: [draft PR #113](https://github.com/sertactan/M10/pull/113). **Do not merge/deploy before confirming Render variable `MERIDYEN_OPENBB_OAUTH_PASSWORD` exists.** Render get_service does NOT expose environment variable presence. Source code/CI cannot prove it; credential confirmation must be made in the Render Environment UI. Never expose its value. Existing legacy bearer must keep working.
2. Only after credentials are verified, switch OAuth live, test authenticated hosted ChatGPT initialize, tools/list, openbb_status, openbb_history(SPY), and openbb_sec_filings(INOD). OpenBB currently intentionally **excluded** from portable PRIVATE plugin MCP manifests because no hosted owner OAuth is yet live.
3. YFinance server-side real OAuth PKCE and INOD daily-bar tests PASSED. Render and GitHub authenticated host-context tools/list evidence is not a true end-user ChatGPT OAuth session. Never label daily quote real time. The owner must authorize ChatGPT OAuth in the client.
4. Social V5 cloud MCP upgraded and tested from external GitHub runner, 4 tools, status call succeeded; 24 original Social checks retained. Its host-side PRIVATE plugin link still requires an actual user session and direct call.
5. Meridyen Equity Research PRIVATE v0.27.3 currently provides /v5-unified-menu and preserved Social/YFinance portable configs. This is **text skill routing**, not server-side orchestration of all 3 into 1 MCP process.
6. Three provider evidence contracts are added at scripts/mobile_provider_evidence.py. Price quotes require symbol, positive value, date and retrieval timestamp. Conflicting/missing date, currency or adjustment prohibits numeric cross-provider comparison. Social is isolated noncanonical research-only.

## 8: S16-C and S16-E
- S16Input currently has **22 normalized model inputs** (core/models/s16_contracts.py); every required input must have value, source ref, observed_at and available_at, valid range and PIT as-of discipline. Composite availability or an as-of date alone does not establish independent PIT.
- `inventory_s16_evidence` returns missing/invalid/future/source/PIT evidence lists. With all claimed inputs, status remains `SOURCE_ASSERTED_READY_NEEDS_INDEPENDENT_AUDIT`, **never canonical-certified**. It does not invoke or alter original S16 V1 math.
- Estimated `S16-E` requires a formally versioned estimator and actual feature inputs; this patch deliberately returns NOT_COMPUTED. `S16-C` remains INCONCLUSIVE until original canonical engine and independent 22-feature evidence agree.

## 9: S16-EA real alerts
- `scripts/s16ea_cloud_evidence_gate.py` (already merged from PR #111) checks 1/5-minute + news source timestamps and as-of leakage; no trading alerts.
- `scripts/s16ea_alert_journal_dryrun.py` is an opt-in **local journal only**, with deterministic idempotency and strict gate; by default dry-run, no notifications, no timer, no remote storage.
- To run 24/7: independently lawful/provisioned intraday source and timestamped news baseline, persistent durable database, scheduler + cost limits, idempotency across workers, notification channel with user opt-in, and independently tested replay/backtest. Render Free web instances may idle. Do not deploy phantom alerts.

## 10: Daily infrastructure check
- `.github/workflows/meridyen-remote-mcp-health.yml`: schedule `20 23 * * *`, approximately 08:20 JST on default branch (GitHub schedules can be delayed). Checks three live HTTPS health endpoints, forbidden anonymous MCP list for protected sources, YFinance OAuth discovery, and real Social MCP initialize/list/status.
- No user OAuth secrets, vendor tick data or fee-incurring jobs. Failure is visible as a GitHub Actions failed workflow; **not a promised ChatGPT push notification**. It must merge to main and then have an actual scheduled run before it can be called an operational recurring monitor.

## 11: historic PIT / WF9
- M10 default WF9 desired 2013-01..2024-12 = **144 monthly point-in-time** membership snapshots with delisted equities and ticker identity chains.
- Provider must include market and listing status when it was historically available; current 2026 ticker lists cannot replace historical as-of membership. SEC submissions/companyfacts must respect acceptance/available_at and period_end temporal gates.
- Authoritative adjusted price OHLCV, split/dividend/delisting terminal proceeds and source vintage with licensed provenance must be independently verified. Stooq RAW_ONLY, yfinance retrospective download, or OpenBB short research history cannot be promoted as backtest authority.
- Run `scripts/phase14_dataset_audit.py` on the **real Windows runtime's** operational.db and corresponding Parquet root. GitHub ephemeral runner is not that database. `WF9 COMPLETE_AND_ACTIVATED` requires native original activation evidence; no successful code CI substitute.
- **No actual historical dataset downloaded or certified in this iPhone-only batch.**

## 12: security / rollback
- Do not paste credentials or screenshot secret values into chats, issues or GitHub. Restrict Render ENV visibility.
- OAuth 401 (unauthorized) vs 400 (invalid PKCE/redirect) vs 403 (denied) vs 429 (failed-password throttling) must be treated differently. Production secrets must be rotated if previously exposed.
- OpenBB OAuth PR #113 is staged; rollback is leave PR unmerged, keep old deployed bearer service.
- Social V5 previous known-good Render commit was f7aec2e59ba23e0e93f80ba3ee52a31640866a95, new commit 0f07999a76dc1782ef3a1953cb5f61a9a3563304 validated with limited external post-deploy smoke. Rollback only after verifying known-good build/config compatibility and preserving evidence.
- Never publicly expose `MERIDYEN_MCP_BEARER_TOKEN` or HMAC signing key.
- GitHub test green != hosted ChatGPT account tool invocation success != historical PIT model activation.

**Validated cloud evidence links:**
- [External HTTPS baseline success](https://github.com/sertactan/M10/actions/runs/37860102579)
- [Social post-upgrade success](https://github.com/sertactan/M10/actions/runs/37860488226)
- [OpenBB OAuth staging regression](https://github.com/sertactan/M10/actions/runs/37860626537)
- [Production checklist issue](https://github.com/sertactan/M10/issues/112)
