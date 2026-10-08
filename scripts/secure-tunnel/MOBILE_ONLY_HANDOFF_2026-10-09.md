# Meridyen Mobile-Only Handoff — 2026-10-09

**Objective:** Prepare YFinance, OpenBB V5 and Social V5 Secure MCP Tunnel integration from iPhone using GitHub, Render and ChatGPT Plugins **without needing Windows now**.

## What was verified from connected accounts

- GitHub: `sertactan/M10`, branch `feature/secure-mcp-tunnel-all-integrations` exists.
- Three separate stdio entrypoints are committed on the deployment branches:
  - `deploy/yfinance-mcp-render-free` → `integrations/yfinance-mcp/local_tunnel_stdio.py` (6 tools)
  - `deploy/openbb-v5-mcp-render-free` → `openbb-v5-render/local_tunnel_stdio.py` (OpenBB tools)
  - `deploy/social-v5-render-free` → `social-v5-render/local_tunnel_stdio.py` (Social tools)
- Render workspace `tea-db3qi5navr4c73aqrnrg` has three Free services, all with latest deployment `live`:
  - `meridyen-yfinance-mcp-free` (OAuth-protected public HTTPS MCP)
  - `meridyen-openbb-v5-free` (Bearer-gated public HTTPS MCP)
  - `meridyen-social-v5-free` (public read-only, rate limited)
- Render auto-deploy is **off** for all three. Changes to GitHub deployment branches will NOT automatically deploy to Render.
- PRIVATE `meridyen-equity-research` plugin v0.27.2 still declares the legacy YFinance and Social Render HTTPS endpoints in `mcp.json`; OpenBB is not declared there. This plugin is **not** the separately connected ChatGPT app named `Meridyen`.
- ChatGPT app `Meridyen` previously passed actual `server_info` and `echo` demo tools, but a recent check returned `Tunnel-client has not been seen for 300 seconds`: local Windows client currently unavailable.
- S1 / S2 / S14 / S15.3 / S16 canonical scoring logic was not changed by this migration branch.

## iPhone-side items to do

- [x] Inspect the current PRIVATE plugin manifest and Remote MCP configuration without modifying it.
- [x] Confirm the latest Render deployments are live and all are Free.
- [x] Confirm safe rollback path: retain existing Render services until real tunnels pass ChatGPT tool calls.
- [x] Prepare Windows setup and runner scripts for the three stdio services on an isolated GitHub branch.
- [x] Prepare this mobile handoff with the exact verification gates.
- [ ] **Owner action: revoke any OpenAI Platform API key ever shared in a chat or screenshot.** Create a new restricted Runtime key only when starting the next tunnel. Never share the key with ChatGPT or put it in GitHub/Render.
- [ ] **Owner action: inspect three tunnel-to-ChatGPT workspace associations** in https://platform.openai.com/settings/organization/tunnels, if connection selection fails. The prior demo proved at least one tunnel is reachable in a connected ChatGPT app.
- [ ] **Owner action: check Platform Usage/Billing** so tunnel hosting/API use cannot incur unwanted charges. ChatGPT Plus does not fund Platform usage.

## Windows / trusted Linux host required later (not iPhone-only)

- [ ] Start a 64-bit PowerShell, validate Python 3.11 and Git.
- [ ] Run `scripts/secure-tunnel/Prepare-YFinanceTunnel.ps1` and install six read-only YFinance MCP tools.
- [ ] Stop the existing demo stub so that only one tunnel-client uses the YFinance tunnel ID.
- [ ] Run `scripts/secure-tunnel/Run-YFinanceTunnel.ps1`, pass a **new** runtime key locally and check `doctor`, `/readyz`, and ChatGPT `get_stock_quote(INOD)`.
- [ ] Build/test Social and OpenBB local profiles with `Setup-MeridyenTunnels.ps1` and run on separate ports / processes. Confirm `social_status` and `openbb_status`, plus real upstream one-shot requests.
- [ ] Keep tunnel-client running on an always-on trusted Windows/Linux host. iOS Safari/ChatGPT alone cannot run the daemon 24/7.
- [ ] Only once all three new real tunnels work: detach old Render URLs from private plugin and ChatGPT app, then disable legacy public ingress. Do not delete services or touch production secrets earlier.
- [ ] Verify S16-C fails closed when canonical PIT inputs are absent. Never substitute Yahoo daily bars for canonical data.

## Stop conditions (never claim full migration complete)

- `HTTP 200 ready` for `mcp-stub` does **not** mean YFinance is connected.
- A Render `live` deploy does **not** mean its public API is now private.
- A ChatGPT app marked `Connected` does **not** mean a specific tool is callable.
- Never set `LIVE_CONNECTED` until the real source tool answers inside ChatGPT with auditable timestamps.
- If a step fails, preserve the old services, documents and model formulas; investigate without forcing a switchover.

## Key project links

- [Secure tunnel branch](https://github.com/sertactan/M10/tree/feature/secure-mcp-tunnel-all-integrations/scripts/secure-tunnel)
- [Tunnels management](https://platform.openai.com/settings/organization/tunnels)
- [Runtime API keys](https://platform.openai.com/settings/organization/api-keys)
- [Usage](https://platform.openai.com/usage)
- [Render dashboard](https://dashboard.render.com/)
- [Existing private plugin](https://chatgpt.com/plugins)

This is a status snapshot and safety checklist, not a claim that Windows-side services are running.
