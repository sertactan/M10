"""Opt-in one-shot MCP transport + Yahoo quote diagnostic. No credential logging."""
import asyncio
import logging
import os
import time

import httpx
from oauth_gate import ORIGIN, RESOURCE, SCOPE, _token

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
            log.warning("SMOKE INOD quote http=200 result_error=%s provider_status=%s price=%s as_of=%s",
                        data.get("isError", False), structured.get("status"),
                        structured.get("price", structured.get("close")),
                        structured.get("data_as_of", structured.get("date")))
        except Exception as exc:
            log.warning("SMOKE failed type=%s", type(exc).__name__)
