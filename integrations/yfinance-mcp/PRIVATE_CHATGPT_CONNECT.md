# Meridyen YFinance MCP — Private OAuth deployment

## Service
- Remote MCP: https://meridyen-yfinance-mcp-free.onrender.com/mcp
- Health: https://meridyen-yfinance-mcp-free.onrender.com/health
- Hosted on Render Free, Python MCP SDK 1.x, Streamable HTTP
- Branch: deploy/yfinance-mcp-render-free (kept separate from main M10)
- Six read-only tools, no broker trading, no paid API
- Yahoo daily data is unofficial and not historical point-in-time canonical.

## Authentication
All /mcp requests require a Bearer access token. Without it, the service returns
401 with a standard RFC 9728 OAuth protected-resource challenge. Supported auth:
OAuth 2.1-style authorization code + PKCE S256 with dynamic client registration,
one-owner password verification, audience/scopes/expiration checks, callback
allowlist for chatgpt.com. OAuth metadata is served at /.well-known paths.

Render environment variable names (NEVER commit values):
- MERIDYEN_OAUTH_PASSWORD — choose a user-controlled random secret >=24 characters
- MERIDYEN_OAUTH_SIGNING_KEY — random signing secret >=40 characters
- MERIDYEN_SMOKE_ON_START — set to 0 after one-shot smoke tests

Never store passwords, OAuth tokens or signing secrets in plugin.json, mcp.json or
GitHub. Rotate the password using Render dashboard → Environment before personal
ChatGPT authorization. Token lifetime is currently 24 hours; reconnecting may
be necessary. On Render Free, pending OAuth authorization codes are in memory and
must be exchanged before the instance is restarted.

## ChatGPT plugin
The PRIVATE Meridyen v0.27.2 already declares this endpoint at mcp.json.
Do not upload an older v0.26 package or overwrite Social V5/OpenBB modules.
Open plugin connection settings, link the YFinance service, complete the OAuth
password login, authorize read-only scope, and start a NEW chat/session to
refresh MCP tools.

## Validation
The optional one-shot server-side smoke tests:
- HTTP unauthenticated tools/list must return 401
- Authorized MCP initialize must return 200
- Authorized MCP tools/list must show six tools
- MCP tools/call(get_stock_quote, symbol=INOD) checks actual Yahoo response
- OAuth PKCE login and code-replay test validates the token exchange

Do not label ChatGPT-end-to-end integration LIVE_CONNECTED until a host-side
authenticated tool call really succeeds. The server-side smoke is independent
of user-side ChatGPT linking. OAuth is a small self-hosted adapter, not a
third-party security audit. Validate licensing before commercial use.
