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

All price records report observation timestamp, source command and NONCANONICAL_RESEARCH_ONLY. Current-download data is not proof of historical availability or survivorship-safe PIT. Actual MCP protocol connectivity to ChatGPT requires separate authenticated connector configuration and a tools/list + tools/call test.
