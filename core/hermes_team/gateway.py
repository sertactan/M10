"""Loopback-only OpenAI-compatible proxy for a single verified FREE LLM.

Hermes must set its *only* model to this custom OpenAI endpoint; disable all
native provider fallbacks, agent-LLM cron jobs and direct provider credentials.
Disabled by default. Never expose this endpoint to the public Internet.
"""
from __future__ import annotations

import hmac
import json
import os
import secrets
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from core.hermes_team.guard import Blocked, Policy, QuotaGuard

ENDPOINTS = {
    "openrouter": "https://openrouter.ai/api/v1/chat/completions",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
}
KEY_ENV = {"openrouter": "OPENROUTER_API_KEY", "gemini": "GEMINI_API_KEY"}


def check_payload(payload: dict, policy: Policy) -> bytes:
    if not isinstance(payload, dict) or payload.get("model") != policy.model:
        raise Blocked("MODEL_OVERRIDE_BLOCKED")
    if payload.get("tools") or payload.get("tool_choice") or payload.get("functions"):
        raise Blocked("TOOL_EXECUTION_NOT_ALLOWED_ON_FREE_PROXY")
    if not isinstance(payload.get("messages"), list) or not payload["messages"]:
        raise Blocked("EMPTY_MESSAGES")
    if payload.get("stream") is True:
        raise Blocked("STREAM_NOT_YET_SUPPORTED")
    if payload.get("n", 1) != 1:
        raise Blocked("MULTIPLE_COMPLETIONS_BLOCKED")
    limit = payload.get("max_tokens", policy.max_output_tokens)
    if type(limit) is not int or limit < 1 or limit > policy.max_output_tokens:
        raise Blocked("MAX_OUTPUT_EXCEEDED")
    allowed = {"model", "messages", "temperature", "max_tokens", "stream"}
    if set(payload) - allowed:
        raise Blocked("UNSUPPORTED_MODEL_PARAMETER")
    if any(not isinstance(m, dict) or m.get("role") not in
           ("system", "developer", "user", "assistant")
           or not isinstance(m.get("content"), str)
           or set(m) - {"role", "content"} for m in payload["messages"]):
        raise Blocked("UNSAFE_MESSAGE_FORMAT")
    safe = {**payload, "stream": False, "max_tokens": limit}
    return json.dumps(safe, ensure_ascii=False).encode("utf-8")


def remote_call(policy: Policy, request_bytes: bytes) -> bytes:
    key = os.environ.get(KEY_ENV[policy.provider], "")
    if not key:
        raise Blocked("PROVIDER_SECRET_MISSING")
    req = urllib.request.Request(
        ENDPOINTS[policy.provider], data=request_bytes,
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        # Bounded response; prevents log/disk/memory blowups.
        raw = resp.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise Blocked("RESPONSE_TOO_LARGE")
        return raw


def perform(payload: dict, *, policy: Policy, guard: QuotaGuard,
            transport=remote_call) -> dict:
    policy.validate(__import__("time").time())
    request_bytes = check_payload(payload, policy)
    # Policy is evaluated *before* any credential use or network activity.
    rid = secrets.token_hex(16)
    guard.reserve(request_id=rid, policy=policy, prompt_bytes=len(request_bytes))
    try:
        data = transport(policy, request_bytes)
        result = json.loads(data)
        if not isinstance(result, dict):
            raise Blocked("INVALID_PROVIDER_RESPONSE")
        return result
    finally:
        guard.finish(rid)


def load_policy(path: Path) -> Policy:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if set(obj) - set(Policy.__dataclass_fields__):
        raise Blocked("UNKNOWN_POLICY_FIELDS")
    return Policy(**obj)


def make_handler(policy: Policy, guard: QuotaGuard, private_key: str):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            # Never log prompts, auth headers, IP, raw provider errors or API keys.
            return

        def _reply(self, status, obj):
            data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path != "/healthz":
                return self._reply(404, {"error": "NOT_FOUND"})
            return self._reply(200, {"status": "DISABLED" if not policy.enabled else "CONFIGURED_NOT_PROVEN"})

        def do_POST(self):
            if self.path != "/v1/chat/completions":
                return self._reply(404, {"error": "NOT_FOUND"})
            header = self.headers.get("Authorization", "")
            if not hmac.compare_digest(header, "Bearer " + private_key):
                return self._reply(401, {"error": "UNAUTHORIZED"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size < 2 or size > policy.max_prompt_bytes:
                    raise Blocked("REQUEST_TOO_LARGE_OR_EMPTY")
                obj = json.loads(self.rfile.read(size))
                self._reply(200, perform(obj, policy=policy, guard=guard))
            except (Blocked, ValueError, KeyError, TypeError, json.JSONDecodeError):
                self._reply(403, {"error": "STRICT_FREE_BLOCKED"})
            except (urllib.error.URLError, TimeoutError, OSError):
                self._reply(503, {"error": "FREE_PROVIDER_UNAVAILABLE_NO_FALLBACK"})

    return Handler


def serve(policy_path: Path, ledger_path: Path) -> None:
    policy = load_policy(policy_path)
    secret = os.environ.get("MERIDYEN_HERMES_GATEWAY_KEY", "")
    if len(secret) < 32:
        raise Blocked("GATEWAY_KEY_REQUIRED_MIN_32_CHARS")
    # Always listen on loopback even if config/environment requests public IP.
    server = ThreadingHTTPServer(("127.0.0.1", 8765),
                                 make_handler(policy, QuotaGuard(ledger_path), secret))
    server.serve_forever()
