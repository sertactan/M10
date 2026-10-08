"""Optional bearer gate for Meridyen Social V5, staged but NOT enabled on Render.

If SOCIAL_MCP_BEARER_TOKEN is absent, preserve current public read-only access.
When it is set on Render, all /mcp calls require that exact token in
Authorization: Bearer <token>. The token must be configured securely in BOTH
the server and the client, without publishing it in mcp.json/GitHub.

This is deliberately separate from canonical models and Social V5 data code.
"""
import hmac
import os


class BearerGuard:
    def __init__(self, app, token=None):
        self.app = app
        self.token = os.environ.get("SOCIAL_MCP_BEARER_TOKEN", "") if token is None else token
        if self.token and len(self.token.encode("utf-8")) < 32:
            raise ValueError("SOCIAL_MCP_BEARER_TOKEN must contain 32+ bytes")
        self.protected = bool(self.token)

    async def __call__(self, scope, receive, send):
        if scope.get("type") not in ("http", "websocket"):
            return await self.app(scope, receive, send)
        path = scope.get("path", "")
        if not (path == "/mcp" or path.startswith("/mcp/")) or not self.protected:
            return await self.app(scope, receive, send)
        # MCP is an HTTP endpoint. Reject unauthenticated WS upgrades as well.
        if scope.get("type") == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        values = [value for key, value in scope.get("headers", ())
                  if key.lower() == b"authorization"]
        supplied = values[0] if len(values) == 1 else b""
        expected = ("Bearer " + self.token).encode("utf-8")
        authorized = len(supplied) <= 512 and hmac.compare_digest(supplied, expected)
        if not authorized:
            body = b'{"error":"unauthorized"}'
            await send({"type": "http.response.start", "status": 401,
                        "headers": [(b"content-type", b"application/json"),
                                    (b"www-authenticate", b'Bearer realm="MeridyenSocialV5"'),
                                    (b"cache-control", b"no-store")]})
            await send({"type": "http.response.body", "body": body})
            return
        await self.app(scope, receive, send)
