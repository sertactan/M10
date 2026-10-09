"""Authenticated *loopback-only* MCP Streamable HTTP control adapter.

Research-only tools; no market order execution, data disclosure or LLM routes.
Never expose this localhost HTTP server directly to the public Internet.
"""
from __future__ import annotations

import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from core.hermes_team.tasks import LocalTasks
from core.hermes_team.paper import preview_paper_position

COMMANDS = ("strategy", "scan", "fundamental", "catalyst", "risk", "learning")
SCHEMA_VERSION = "2025-03-26"
TOOLS = [
    {"name": "meridyen_team_status", "description": "Read research-only service status.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "meridyen_team_submit", "description": "Enqueue a deterministic offline research task.",
     "inputSchema": {"type": "object", "properties": {
         "task": {"type": "string", "enum": list(COMMANDS)}},
         "required": ["task"], "additionalProperties": False}},
    {"name": "meridyen_team_tick", "description": "Run at most one offline task; no paid API calls.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "meridyen_team_job", "description": "Read durable status by opaque job ID.",
     "inputSchema": {"type": "object", "properties": {
         "job_id": {"type": "string", "pattern": "^[a-f0-9]{32}$"}},
         "required": ["job_id"], "additionalProperties": False}},
    {"name": "meridyen_paper_preview", "description": "Deterministic user-input scenario. Not a market signal or broker order.",
     "inputSchema": {"type": "object", "properties": {
         "symbol": {"type": "string"}, "as_of": {"type": "string"},
         "price": {"type": "number"}, "stop": {"type": "number"},
         "capital": {"type": "number"}, "risk_fraction": {"type": "number"},
         "spread_fraction": {"type": "number"}, "slippage_fraction": {"type": "number"},
         "fee_usd": {"type": "number"}},
         "required": ["symbol", "as_of", "price", "stop", "capital", "risk_fraction",
                      "spread_fraction", "slippage_fraction", "fee_usd"],
         "additionalProperties": False}},
]


def call_tool(queue: LocalTasks, name: str, args: dict) -> dict:
    if not isinstance(args, dict):
        raise ValueError("INVALID_ARGUMENTS")
    if name == "meridyen_team_status" and not args:
        return {"state": "RESEARCH_ONLY", "llm_enabled": False, "live_trading": False,
                "cloud_deployed": False, "roles": 6, "tasks": queue.summary()}
    if name == "meridyen_team_submit" and set(args) == {"task"} and args["task"] in COMMANDS:
        return {"job_id": queue.submit(args["task"]), "state": "QUEUED"}
    if name == "meridyen_team_tick" and not args:
        return queue.dispatch_one() or {"state": "NO_PENDING_WORK"}
    if name == "meridyen_team_job" and set(args) == {"job_id"} and isinstance(args["job_id"], str):
        job_id = args["job_id"]
        if len(job_id) == 32 and all(c in "0123456789abcdef" for c in job_id):
            return queue.status(job_id) or {"state": "NOT_FOUND"}
    if name == "meridyen_paper_preview":
        return preview_paper_position(args)
    raise ValueError("TOOL_ARGUMENTS_INVALID")


def respond_jsonrpc(request: dict, queue: LocalTasks) -> dict | None:
    if not isinstance(request, dict) or request.get("jsonrpc") != "2.0":
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid Request"}}
    mid = request.get("id")
    method = request.get("method")
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": mid, "result": {
            "protocolVersion": SCHEMA_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "meridyen-hermes-local", "version": "0.2.0"}}}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": mid, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        try:
            params = request["params"]
            value = call_tool(queue, params["name"], params.get("arguments", {}))
            return {"jsonrpc": "2.0", "id": mid, "result": {
                "content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}],
                "isError": False}}
        except (ValueError, KeyError, TypeError):
            return {"jsonrpc": "2.0", "id": mid, "result": {
                "content": [{"type": "text", "text": "INCONCLUSIVE: Invalid tool call"}],
                "isError": True}}
    return {"jsonrpc": "2.0", "id": mid,
            "error": {"code": -32601, "message": "Method not found"}}


def handler_factory(queue: LocalTasks, secret: str):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            return  # Never log secrets, prompts, or client payloads.

        def _send(self, code: int, payload: dict):
            raw = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self):
            if self.path != "/mcp":
                return self._send(404, {"error": "NOT_FOUND"})
            if not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + secret):
                return self._send(401, {"error": "UNAUTHORIZED"})
            try:
                n = int(self.headers.get("Content-Length", "0"))
                if n <= 0 or n > 16_384:
                    raise ValueError("PAYLOAD_SIZE")
                req = json.loads(self.rfile.read(n))
                outcome = respond_jsonrpc(req, queue)
                if outcome is None:
                    return self._send(200, {})
                return self._send(200, outcome)
            except (ValueError, UnicodeError, TypeError):
                return self._send(400, {"error": "INVALID_JSON"})

        def do_GET(self):
            return self._send(405, {"error": "POST_ONLY"})

    return Handler


def serve(ledger: Path) -> None:
    token = os.environ.get("MERIDYEN_LOCAL_MCP_TOKEN", "")
    if len(token) < 32:
        raise RuntimeError("MCP_TOKEN_REQUIRED_IN_PRIVATE_ENV")
    server = ThreadingHTTPServer(("127.0.0.1", 8876),
                                 handler_factory(LocalTasks(ledger), token))
    server.serve_forever()
