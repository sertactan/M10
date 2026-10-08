# Meridyen OpenBB V5 FREE MCP sidecar

Isolated code in a deployment branch. Read-only; no edits to M10 or canonical S15/S16 models; no trades, no paid data providers, no backfill of PIT scores.

## Render configuration
- Runtime: Python; plan: Free; branch: deploy/openbb-v5-mcp-render-free
- Build: pip install -r openbb-v5-render/requirements.txt && openbb-build && python -m py_compile openbb-v5-render/server.py
- Start: cd openbb-v5-render && uvicorn server:app --host 0.0.0.0 --port $PORT --workers 1
- Secret environment variable: MERIDYEN_MCP_BEARER_TOKEN, at least 32 characters, never committed.
- HTTPS MCP: /mcp, requires Authorization: Bearer TOKEN
- Public GET /healthz shows internal registration and actual optional startup SPY test outcome.

## Tools
- openbb_status (package/provider status)
- openbb_history (Cboe/Nasdaq historical bar data, <=93-day range)
- openbb_spy_test (real Cboe SPY historical fetch)
- openbb_sec_filings (keyless official SEC 10-K/10-Q filing links, symbol validated)

All price records report observation timestamp, source command and NONCANONICAL_RESEARCH_ONLY. Current-download data is not proof of historical availability or survivorship-safe PIT. Actual MCP protocol connectivity to ChatGPT requires separate authenticated connector configuration and a tools/list + tools/call test.

## Verified Render tests — 2026-10-08 UTC

Latest executed startup probes (not generated/synthetic data):

| Capability | Source | Result | Coverage |
|---|---|---|---|
| Authenticated local MCP handshake + tools/list + tools/call | Render loopback streamable HTTP | PASS | 4 tools exposed: openbb_status, openbb_history, openbb_spy_test, openbb_sec_filings |
| SPY price history | OpenBB V5 Cboe | UPSTREAM_FETCH_VERIFIED | 9 daily bars, latest 2026-10-07 |
| INOD price history | OpenBB V5 Nasdaq | UPSTREAM_FETCH_VERIFIED | 12 daily bars, latest 2026-10-07 |
| CRMD price history | OpenBB V5 Nasdaq | UPSTREAM_FETCH_VERIFIED | 12 daily bars, latest 2026-10-07 |
| TMDX price history | OpenBB V5 Nasdaq | UPSTREAM_FETCH_VERIFIED | 12 daily bars, latest 2026-10-07 |
| INOD 10-K / 10-Q listing | OpenBB V5 SEC | UPSTREAM_FETCH_VERIFIED | 4 filing links within 400 days |

### Connection limitation

This is NOT an end-to-end ChatGPT connection. The protected `/mcp` URL requires a static Bearer token and **does not implement OAuth**. ChatGPT's custom MCP connector supports OAuth or no authentication, not a user-provided arbitrary static API key. Do not put the Render bearer token into source or plugin manifests. The existing PRIVATE plugin's `mcp.json` has **not** been changed to advertise a broken OpenBB connection.

To finish ChatGPT connection, implement and security-test proper OAuth 2.1/PKCE with an owner-authorized login, OR obtain user consent for a separate limited, rate-controlled, anonymous *public-only* MCP endpoint. Preserve the protected admin/server endpoint. Report actual tools/list and tools/call tests after configuration.

### Model/PIT caveats

All OpenBB price records and SEC links are `NONCANONICAL_RESEARCH_ONLY`, `pit_valid=false`, `canonical_eligible=false`. No proof of past historical availability, complete delisted universe, or S15/S16 canonical score exists. Windows M10 local database import remains unconnected.
