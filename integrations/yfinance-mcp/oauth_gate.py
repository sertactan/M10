"""Single-owner OAuth 2.1 PKCE gate for Meridyen's read-only MCP service.

Designed for a *single* ChatGPT user. It is intentionally fail-closed unless
the login password and HMAC signing secret are configured in Render ENV.
No brokerage credentials, public anonymous data tools, or secrets in source.
"""
import base64
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import threading
import time
from collections import defaultdict, deque
from urllib.parse import urlencode, urlparse

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.routing import Route

ORIGIN = "https://meridyen-yfinance-mcp-free.onrender.com"
RESOURCE = ORIGIN + "/mcp"
SCOPE = "yfinance:read"
CLIENT = "meridyen-chatgpt-public"
CIMD = "https://chatgpt.com/oauth/client.json"
PASSWORD = os.environ.get("MERIDYEN_OAUTH_PASSWORD", "")
SIGN_KEY = os.environ.get("MERIDYEN_OAUTH_SIGNING_KEY", "")
# Never fall back to demo credentials.
if len(PASSWORD) < 24 or len(SIGN_KEY) < 40:
    raise RuntimeError("Meridyen OAuth credentials missing: fail closed")

pending = {}
codes = {}
attempts = defaultdict(deque)
lock = threading.RLock()


def _b64(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _unb64(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _token(payload):
    header = _b64(b'{"alg":"HS256","typ":"JWT"}')
    body = _b64(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    message = (header + "." + body).encode()
    sig = _b64(hmac.new(SIGN_KEY.encode(), message, hashlib.sha256).digest())
    return header + "." + body + "." + sig


def verify_token(value):
    try:
        header, body, mac = value.split(".")
        valid = _b64(hmac.new(SIGN_KEY.encode(), (header + "." + body).encode(),
                              hashlib.sha256).digest())
        if not hmac.compare_digest(valid, mac):
            return False
        if _unb64(header) != b'{"alg":"HS256","typ":"JWT"}':
            return False
        claims = json.loads(_unb64(body))
        return (claims.get("iss") == ORIGIN and
                claims.get("aud") == RESOURCE and
                claims.get("scope") == SCOPE and
                claims.get("sub") == "meridyen-owner" and
                isinstance(claims.get("exp"), int) and
                claims["exp"] > int(time.time()))
    except (ValueError, TypeError, KeyError, UnicodeError):
        return False


def _redirect_ok(uri):
    try:
        u = urlparse(uri)
        return (u.scheme == "https" and u.hostname == "chatgpt.com" and
                u.username is None and u.password is None and
                u.port in (None, 443) and
                (u.path.startswith("/oauth/") or u.path.startswith("/connector/oauth/") or u.path == "/connector_platform_oauth_redirect") and not u.fragment)
    except ValueError:
        return False


def _client_ok(value):
    return value == CLIENT or value == CIMD or bool(
        re.fullmatch(r"https://chatgpt\.com/oauth/[A-Za-z0-9_-]+/client\.json", value))


def _json(data, status=200):
    return JSONResponse(data, status_code=status, headers={"Cache-Control": "no-store"})


async def resource_metadata(request: Request):
    return _json({
        "resource": RESOURCE, "authorization_servers": [ORIGIN],
        "scopes_supported": [SCOPE],
    })


async def auth_metadata(request: Request):
    return _json({
        "issuer": ORIGIN,
        "authorization_endpoint": ORIGIN + "/authorize",
        "token_endpoint": ORIGIN + "/token",
        "registration_endpoint": ORIGIN + "/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
        "scopes_supported": [SCOPE],
    })


async def register(request: Request):
    try:
        data = await request.json()
    except Exception:
        return _json({"error": "invalid_client_metadata"}, 400)
    uris = data.get("redirect_uris", [])
    if not isinstance(uris, list) or not uris or not all(
        isinstance(uri, str) and _redirect_ok(uri) for uri in uris
    ):
        return _json({"error": "invalid_redirect_uri"}, 400)
    if "authorization_code" not in data.get("grant_types", ["authorization_code"]):
        return _json({"error": "invalid_client_metadata"}, 400)
    return _json({
        "client_id": CLIENT, "client_name": "Meridyen ChatGPT",
        "redirect_uris": uris, "grant_types": ["authorization_code"],
        "response_types": ["code"], "token_endpoint_auth_method": "none",
    }, 201)


async def authorize(request: Request):
    q = request.query_params
    client = q.get("client_id", "")
    redir = q.get("redirect_uri", "")
    chall = q.get("code_challenge", "")
    if not (_client_ok(client) and _redirect_ok(redir) and
            q.get("response_type") == "code" and
            q.get("code_challenge_method") == "S256" and
            re.fullmatch(r"[A-Za-z0-9_-]{43}", chall) and
            q.get("resource", RESOURCE) == RESOURCE and
            SCOPE in q.get("scope", SCOPE).split()):
        return _json({"error": "invalid_request"}, 400)
    key = secrets.token_urlsafe(30)
    with lock:
        pending[key] = {
            "created": time.time(), "client": client, "redirect_uri": redir,
            "challenge": chall, "state": q.get("state", ""),
        }
        # Bound in-process pending transactions.
        if len(pending) > 1000:
            for old in sorted(pending, key=lambda k: pending[k]["created"])[:500]:
                pending.pop(old, None)
    body = ('''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width">
<title>Meridyen account authorization</title></head><body>
<h2>Meridyen YFinance — private access</h2>
<p>Read-only market research (yfinance:read). No brokerage orders.</p>
<form action="/authorize/login" method="post">
<input type="hidden" name="ticket" value="''' + html.escape(key, quote=True) + '''">
<label>Owner password <input type="password" name="password" required
autocomplete="current-password"></label>
<button type="submit">Authorize ChatGPT</button>
</form></body></html>''')
    return HTMLResponse(body, headers={
        "Cache-Control": "no-store",
        "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
    })


async def login(request: Request):
    form = await request.form()
    ticket = str(form.get("ticket", ""))
    password = str(form.get("password", ""))
    peer = (request.client.host if request.client else "unknown")
    now = time.time()
    with lock:
        hits = attempts[peer]
        while hits and hits[0] < now - 900:
            hits.popleft()
        if len(hits) >= 8:
            return _json({"error": "too_many_attempts"}, 429)
        hits.append(now)
        item = pending.get(ticket)
        if not item or now - item["created"] > 300:
            return _json({"error": "expired_authorization"}, 400)
        if not hmac.compare_digest(password.encode(), PASSWORD.encode()):
            return _json({"error": "access_denied"}, 403)
        pending.pop(ticket, None)
        code = secrets.token_urlsafe(32)
        codes[hashlib.sha256(code.encode()).hexdigest()] = dict(item, created=now)
    args = {"code": code, "iss": ORIGIN}
    if item["state"]:
        args["state"] = item["state"]
    sep = "&" if "?" in item["redirect_uri"] else "?"
    return RedirectResponse(item["redirect_uri"] + sep + urlencode(args), status_code=303,
                            headers={"Cache-Control": "no-store"})


async def token(request: Request):
    form = await request.form()
    code = str(form.get("code", ""))
    client = str(form.get("client_id", ""))
    redir = str(form.get("redirect_uri", ""))
    verifier = str(form.get("code_verifier", ""))
    if (form.get("grant_type") != "authorization_code" or
            form.get("resource", RESOURCE) != RESOURCE or
            not re.fullmatch(r"[A-Za-z0-9._~-]{43,128}", verifier)):
        return _json({"error": "invalid_request"}, 400)
    with lock:
        item = codes.pop(hashlib.sha256(code.encode()).hexdigest(), None)
    if (not item or time.time() - item["created"] > 300 or
            item["client"] != client or item["redirect_uri"] != redir):
        return _json({"error": "invalid_grant"}, 400)
    digest = _b64(hashlib.sha256(verifier.encode()).digest())
    if not hmac.compare_digest(digest, item["challenge"]):
        return _json({"error": "invalid_grant"}, 400)
    access = _token({
        "iss": ORIGIN, "aud": RESOURCE, "sub": "meridyen-owner",
        "scope": SCOPE, "exp": int(time.time()) + 86400,
        "iat": int(time.time()), "jti": secrets.token_hex(16),
    })
    return _json({"access_token": access, "token_type": "Bearer",
                  "expires_in": 86400, "scope": SCOPE})


class OAuthGate:
    """Protect every Streamable HTTP operation including initialize/tools/list."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "").rstrip("/")
        if scope["type"] != "http" or path != "/mcp":
            return await self.app(scope, receive, send)
        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        origin = headers.get(b"origin", b"").decode("latin1")
        if origin and origin not in ("https://chatgpt.com", "https://chat.openai.com"):
            return await _json({"error": "origin_forbidden"}, 403)(scope, receive, send)
        authorization = headers.get(b"authorization", b"").decode("latin1")
        valid = authorization.startswith("Bearer ") and verify_token(authorization[7:])
        if not valid:
            response = _json({"error": "unauthorized"}, 401)
            response.headers["WWW-Authenticate"] = (
                'Bearer resource_metadata="' + ORIGIN +
                '/.well-known/oauth-protected-resource", scope="' + SCOPE + '"'
            )
            return await response(scope, receive, send)
        return await self.app(scope, receive, send)


OAUTH_ROUTES = [
    Route("/.well-known/oauth-protected-resource", resource_metadata, methods=["GET"]),
    Route("/.well-known/oauth-protected-resource/mcp", resource_metadata, methods=["GET"]),
    Route("/.well-known/oauth-authorization-server", auth_metadata, methods=["GET"]),
    Route("/.well-known/openid-configuration", auth_metadata, methods=["GET"]),
    Route("/register", register, methods=["POST"]),
    Route("/authorize", authorize, methods=["GET"]),
    Route("/authorize/login", login, methods=["POST"]),
    Route("/token", token, methods=["POST"]),
]
