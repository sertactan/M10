"""Opt-in one-shot MCP transport + Yahoo quote diagnostic. No credential logging."""
import asyncio
import hashlib
import base64
import re
from urllib.parse import urlparse, parse_qs
import logging
import os
import time

import httpx
from oauth_gate import ORIGIN, RESOURCE, SCOPE, CLIENT, _token

log = logging.getLogger("meridyen.mcp.smoke")


async def run():
    await asyncio.sleep(5)
    port = os.getenv("PORT", "10000")
    base = "http://127.0.0.1:" + port + "/mcp"
    payload = {
        "iss": ORIGIN, "aud": RESOURCE, "scope": SCOPE,
        "sub": "meridyen-owner", "exp": int(time.time()) + 300,
        "iat": int(time.time()), "jti": "startup-smoke",
    }
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "Authorization": "Bearer " + _token(payload),
    }
    async with httpx.AsyncClient(timeout=45) as client:
        try:
            noauth = await client.post(base, json={
                "jsonrpc": "2.0", "id": 0, "method": "tools/list", "params": {}
            }, headers={"Accept": headers["Accept"], "Content-Type": "application/json"})
            log.warning("SMOKE unauthenticated_tools_list http=%s", noauth.status_code)
            init = await client.post(base, headers=headers, json={
                "jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                           "clientInfo": {"name": "meridyen-smoke", "version": "1.0"}}
            })
            log.warning("SMOKE initialize http=%s", init.status_code)
            listing = await client.post(base, headers=headers, json={
                "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}
            })
            names = []
            if listing.status_code == 200:
                names = [x.get("name") for x in listing.json().get("result", {}).get("tools", [])]
            log.warning("SMOKE tools_list http=%s count=%s names=%s",
                        listing.status_code, len(names), ",".join(names))
            if "get_stock_quote" not in names:
                log.warning("SMOKE quote skipped: tool not discovered")
                return
            quote = await client.post(base, headers=headers, json={
                "jsonrpc": "2.0", "id": 3, "method": "tools/call",
                "params": {"name": "get_stock_quote", "arguments": {"symbol": "INOD"}}
            })
            if quote.status_code != 200:
                log.warning("SMOKE INOD quote http=%s", quote.status_code)
                return
            data = quote.json().get("result", {})
            structured = data.get("structuredContent", {})
            if not structured:
                for item in data.get("content", []):
                    if item.get("type") == "text":
                        try:
                            import json
                            structured = json.loads(item["text"])
                        except (ValueError, KeyError):
                            structured = {}
                        break
            # Only summary fields. No raw upstream payload or secrets.
            log.warning("SMOKE INOD quote http=200 result_error=%s provider_status=%s price=%s bar_date=%s retrieved_at_utc=%s real_time_verified=%s",
                        data.get("isError", False), structured.get("status"),
                        structured.get("price", structured.get("close")),
                        structured.get("bar_date"), structured.get("retrieved_at_utc"),
                        structured.get("real_time_verified"))
            # Exercise real OAuth PKCE registration, password consent, code exchange,
            # replay rejection, token-gated tool discovery. No secret values logged.
            redirect = "https://chatgpt.com/connector/oauth/meridyen-smoke"
            reg = await client.post("http://127.0.0.1:" + port + "/register", json={
                "redirect_uris": [redirect], "grant_types": ["authorization_code"],
                "response_types": ["code"], "token_endpoint_auth_method": "none"
            })
            log.warning("SMOKE OAuth register http=%s", reg.status_code)
            verifier = "A" * 64
            chall = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
            auth_url = "http://127.0.0.1:" + port + "/authorize"
            auth = await client.get(auth_url, params={
                "client_id": CLIENT, "redirect_uri": redirect, "response_type": "code",
                "scope": SCOPE, "resource": RESOURCE, "state": "smoke-state",
                "code_challenge": chall, "code_challenge_method": "S256"
            })
            ticket_match = re.search(r'name="ticket" value="([^"]+)"', auth.text)
            log.warning("SMOKE OAuth authorize http=%s ticket=%s", auth.status_code, bool(ticket_match))
            if not ticket_match:
                return
            consent = await client.post("http://127.0.0.1:" + port + "/authorize/login",
                                        data={"ticket": ticket_match.group(1),
                                              "password": os.environ["MERIDYEN_OAUTH_PASSWORD"]},
                                        follow_redirects=False)
            callback = urlparse(consent.headers.get("Location", ""))
            args = parse_qs(callback.query)
            log.warning("SMOKE OAuth consent http=%s state_match=%s",
                        consent.status_code, args.get("state") == ["smoke-state"])
            auth_code = args.get("code", [""])[0]
            if not auth_code:
                return
            token_url = "http://127.0.0.1:" + port + "/token"
            form = {"grant_type": "authorization_code", "code": auth_code,
                    "client_id": CLIENT, "redirect_uri": redirect,
                    "resource": RESOURCE, "code_verifier": verifier}
            ex = await client.post(token_url, data=form)
            token = ex.json().get("access_token", "") if ex.status_code == 200 else ""
            log.warning("SMOKE OAuth PKCE token http=%s present=%s", ex.status_code, bool(token))
            replay = await client.post(token_url, data=form)
            log.warning("SMOKE OAuth code_replay http=%s", replay.status_code)
            if token:
                authed = await client.post(base, headers=dict(headers, Authorization="Bearer " + token), json={
                    "jsonrpc": "2.0", "id": 4, "method": "tools/list", "params": {}
                })
                log.warning("SMOKE OAuth issued_token tools_list http=%s", authed.status_code)
        except Exception as exc:
            log.warning("SMOKE failed type=%s", type(exc).__name__)
