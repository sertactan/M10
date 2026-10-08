# OpenBB V5 owner OAuth — staged, opt-in

Status: **source-only until credentials exist and real hosted ChatGPT OAuth succeeds**.

The original `MERIDYEN_MCP_BEARER_TOKEN` gate stays active for existing
authenticated local service and the localhost OpenBB V5 MCP smoke. No bearer is
written into plugin files or GitHub.

This staged branch adds RFC-style OAuth discovery endpoints with a single-user
password + PKCE/S256. It reuses the existing server-side strong bearer as the HMAC
JWT signing secret (never returned to clients). All actual MCP commands remain
read-only and NONCANONICAL.

## From the iPhone
1. Render dashboard > `meridyen-openbb-v5-free` > Environment.
2. Add `MERIDYEN_OPENBB_OAUTH_PASSWORD` as a **new, unique, strong** secret of
   at least 24 characters. Never paste it into a ChatGPT message, source, issue,
   screenshot or public logs. Do not change the existing bearer token.
3. Merge this branch only after its CI is green and secret is provisioned.
4. Trigger a manual Render deployment (auto-deploy currently off). Confirm
   `GET /healthz` reports `owner_oauth_enabled: true`.
5. Connect `https://meridyen-openbb-v5-free.onrender.com/mcp` to the PRIVATE
   plugin/ChatGPT connector, authorize `openbb:read` and verify *real hosted*
   `tools/list` + `openbb_status` + SPY + SEC call.
6. Only then include the endpoint in the plugin's portable MCP manifests and
   declare OpenBB HOST_CONNECTED. Before this, remain STAGED.

Security: redirect_uri strictly chatgpt.com allowlisted, authorization code
5-min single use, token 24-hour validity, failed-password throttle, no password
logging, no anonymous /mcp. Codes remain in memory and expire on instance
restart. If password ENV absent, OAuth consent returns 503; existing bearer
works. Avoid paid API keys, brokerage access, S16 score interpolation.

This does not implement refresh_token, multi-user SSO, durable token invalidation,
DDoS mitigation or full security audit.
