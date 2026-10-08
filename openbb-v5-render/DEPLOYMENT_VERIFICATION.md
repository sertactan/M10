# Meridyen OpenBB V5 FREE — verified cloud deployment

Date: 2026-10-08 15:12 UTC (2026-10-09 Japan).

## Source and service
- Render Free: meridyen-openbb-v5-free, service ID srv-db3r22tg1s2s73bhfl3g
- Branch: deploy/openbb-v5-mcp-render-free; commit f01b4b789da93da38837bc6ec4e0292551b76121
- HTTPS: https://meridyen-openbb-v5-free.onrender.com/mcp
- Bearer authentication: required; token stored only as Render environment secret
- OpenBB Core 2.0.1; Cboe 2.0.0; Nasdaq 2.0.0; SEC 2.0.0; FastMCP 3.4.0

## Actual runtime proof from Render logs
- Latest deploy: LIVE, Render event deploy_ended succeeded.
- Streamable MCP HTTP loopback smoke: initialize 200; initialized notification 202; tools/list 200; tools/call openbb_status 200.
- MCP_WIRE_SMOKE: MCP_PROTOCOL_VERIFIED_LOCAL, 2026-10-08T15:12:04Z
- Discovered tools: openbb_history, openbb_spy_test, openbb_status.
- OPENBB_SPY_PROBE: UPSTREAM_FETCH_VERIFIED on keyless Cboe via OpenBB V5, 9 bars, last bar 2026-10-07; checked 2026-10-08T15:12:34Z; no upstream error.

## Scope and explicit limitations
- **Not verified:** an external ChatGPT hosted MCP connector, its authenticated tools/list/tools/call over the public HTTPS endpoint, or direct Meridyen plugin invocation.
- **Not verified:** PIT historical vintages, survivorship/delisted coverage, authoritative adjustment or 1-minute real-time market feed.
- The original Meridyen private plugin v0.27.0 was **not changed** by this deployment. Neither Social nor YFinance Render service was modified.
- All results are NONCANONICAL_RESEARCH_ONLY. S1/S2/S14/S15/S16 model logic untouched.
- Never put the Render bearer token into this public repository, issues, examples or logs.
