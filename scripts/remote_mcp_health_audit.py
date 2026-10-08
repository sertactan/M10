"""External, secret-free verification of three Meridyen Render MCP endpoints.

This is a narrow public HTTPS transport/protocol smoke. It NEVER claims hosted
ChatGPT OAuth user authorization, market-data freshness, PIT or S16 readiness.
"""
from __future__ import annotations
import json
import sys
import time
import urllib.error
import urllib.request

SERVICES = {
    "OpenBB": "https://meridyen-openbb-v5-free.onrender.com",
    "YFinance": "https://meridyen-yfinance-mcp-free.onrender.com",
    "Social": "https://meridyen-social-v5-free.onrender.com",
}
HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
    "MCP-Protocol-Version": "2025-03-26",
}


def request(url: str, *, method: str = "GET", payload=None, headers=None):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method=method,
                                  headers=headers or {"Accept": "application/json"})
    last = None
    for i in range(3):
        try:
            with urllib.request.urlopen(req, timeout=50) as res:
                return res.status, res.read(524288).decode("utf-8")
        except urllib.error.HTTPError as error:
            # An expected auth rejection is a valuable security test.
            value = (error.code, error.read(8192).decode("utf-8", errors="replace"))
            if error.code not in (429, 502, 503, 504):
                return value
            last = value
        except (urllib.error.URLError, TimeoutError) as error:
            last = (0, type(error).__name__)
        if i < 2:
            time.sleep(7)
    raise RuntimeError(f"External endpoint failed after bounded retries: {url} status={last[0]}")


def rpc(method: str, params=None, id: int = 1):
    return {"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}}


def result_json(raw):
    text = raw.strip()
    if text.startswith("data:"):
        text = next((line[5:].strip() for line in text.splitlines() if line.startswith("data:")), "")
    return json.loads(text)


def verify():
    results = {}
    for name, origin in SERVICES.items():
        route = {"OpenBB": "/healthz", "YFinance": "/health",
                 "Social": "/health"}[name]
        status, body = request(origin + route)
        assert status == 200, (name, "health", status)
        data = json.loads(body)
        if name == "OpenBB":
            assert data.get("status") == "READY", data
            assert "openbb_history" in data.get("registered_tools", []), data
        elif name == "YFinance":
            assert data.get("status") == "ready", data
            assert data.get("oauth_required") is True, data
            assert data.get("point_in_time_canonical") is False, data
        else:
            assert data.get("healthy") is True, data
        results[name] = {"health_http": status, "health_contract": "PASS"}

    # Never request a token or store authorization secrets in Actions.
    for name in ("OpenBB", "YFinance"):
        status, _ = request(SERVICES[name] + "/mcp", method="POST",
                            payload=rpc("tools/list"), headers=HEADERS)
        assert status == 401, (name, "AUTHORIZATION_FAIL_OPEN", status)
        results[name]["unauthenticated_tools_list"] = "DENIED_401"

    status, body = request(SERVICES["YFinance"] +
       "/.well-known/oauth-protected-resource")
    assert status == 200, status
    resource = json.loads(body)
    assert resource.get("resource") == SERVICES["YFinance"] + "/mcp", resource
    results["YFinance"]["oauth_discovery"] = "PASS"

    # The Social MCP service is public and read-only; verify its real remote
    # Streamable-HTTP handshake, tool discovery and side-effect-free status.
    status, body = request(SERVICES["Social"] + "/mcp", method="POST",
                           payload=rpc("initialize", {
                               "protocolVersion": "2025-03-26",
                               "capabilities": {},
                               "clientInfo": {"name": "meridyen-remote-audit",
                                              "version": "1.0"}}, 1),
                           headers=HEADERS)
    assert status == 200, ("social_initialize", status, body[:160])
    initialized = result_json(body)
    assert initialized.get("result", {}).get("protocolVersion"), initialized

    status, body = request(SERVICES["Social"] + "/mcp", method="POST",
                           payload=rpc("tools/list", id=2), headers=HEADERS)
    assert status == 200, ("social_tools_list", status)
    listing = result_json(body)
    names = {item.get("name") for item in listing.get("result", {}).get("tools", [])}
    assert {"social_status", "social_bluesky", "social_mastodon", "social_scan"} <= names, names

    status, body = request(SERVICES["Social"] + "/mcp", method="POST",
                           payload=rpc("tools/call",
                                       {"name": "social_status", "arguments": {}}, 3),
                           headers=HEADERS)
    assert status == 200, ("social_status", status)
    result = result_json(body).get("result", {})
    assert not result.get("isError", False), result
    results["Social"].update(remote_mcp_handshake="PASS",
                              remote_tools_list=len(names),
                              social_status_call="PASS")

    print(json.dumps({"status": "EXTERNAL_HTTPS_SMOKE_PASSED",
        "scope": "NO_HOSTED_CHATGPT_OAUTH_OR_CANONICAL_DATA_CLAIM",
        "services": results}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(verify())
    except Exception as exc:
        print(json.dumps({"status": "EXTERNAL_HTTPS_SMOKE_FAILED",
                          "type": type(exc).__name__,
                          "reason": str(exc)[:300]}, indent=2))
        sys.exit(2)
