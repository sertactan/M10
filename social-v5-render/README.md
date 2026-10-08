# Meridyen Social V5 FREE — Render-sidecar (private branch)

This branch deliberately leaves all existing Meridyen S1/S2/S14/S15.3/S16/S16-EA code and default branch unchanged.

## Sources
- `social_v5_free.py`: verbatim original MERIDYEN_SOCIAL_V5_FREE V0.26.0 skill source.
- `tests/test_social_v5_free.py`: verbatim original 22 offline unittest cases.
- `server.py`: minimal read-only Streamable HTTP MCP wrapper.

## Build on Render Free
- Repository: `sertactan/meridyen-one-v2-5` (PRIVATE)
- Branch: `social-v5-free-render-20261008`
- Plan: FREE, Region: Singapore
- Runtime: Python
- Build: `pip install -r social-v5-render/requirements.txt && python -m unittest discover -s social-v5-render/tests -p 'test_*.py' -v`
- Start: `sh -c 'cd social-v5-render && uvicorn server:app --host 0.0.0.0 --port "${PORT:-10000}"'`
- Endpoint: `https://<assigned-hostname>/mcp`; health: `/health`.
- `RENDER_EXTERNAL_HOSTNAME` should be the actual hostname, auto-set by Render.

## Tools
- `social_status`: source/connection/constraint inventory.
- `social_bluesky(ticker, limit)`: one-shot public GET.
- `social_mastodon(ticker, hashtag, limit)`: one-shot public hashtag GET.
- `social_scan(ticker)`: 2 source attempts + **NONCANONICAL** V5 analysis. No historical baseline unless independently captured.

## Safety and costs
- **No paid API keys; no database; no trade calls; no model changes.**
- A hard global cap of 24 external GET calls/hour and a 180 s in-memory cache.
- No silent retry, backfill, scheduler, streaming, bot, scraper, or private-message access.
- Free web services sleep after 15min inactivity. The cache is ephemeral, NOT a PIT archive. Long-term provenance and historical backtests need separate lawful, timestamped storage.
- Public read-only no-auth endpoint; anybody knowing the service URL could use it until throttled. Keep plugin **private**, don't attach private datasets, and set Render billing budget controls or avoid a payment method to enforce $0 spend.
- Bluesky or Mastodon can restrict/deny anonymous calls; return source-unavailable, do not fabricate results.
- This is a separate MCP endpoint. It does not auto-install inside the existing private ChatGPT Meridyen plugin; attach via ChatGPT Custom MCP/Plugin Creator after successful health/MCP verification.
