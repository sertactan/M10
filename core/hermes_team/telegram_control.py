"""Minimal authenticated Telegram research-only command adapter.

No webhook exposure, polling or message delivery by default. Incoming update
handling and outbound transmission are separate explicit opt-in operations.
"""
from __future__ import annotations

import json
import os
import urllib.request
from core.hermes_team.tasks import LocalTasks


def interpret_update(update: dict, *, allowed_chat: str, queue: LocalTasks) -> str | None:
    if not isinstance(update, dict):
        return None
    message = update.get("message")
    if not isinstance(message, dict):
        return None
    chat = message.get("chat") or {}
    if str(chat.get("id", "")) != str(allowed_chat) or not allowed_chat:
        return None
    if message.get("from", {}).get("is_bot") is True:
        return None
    cmd = message.get("text")
    if not isinstance(cmd, str) or len(cmd) > 100:
        return None
    command = cmd.strip().split()
    if not command:
        return None
    verb = command[0].split("@")[0].lower()
    if verb == "/status" and len(command) == 1:
        counts = queue.summary()
        return (f"Meridyen Hermes: local research-only; "
                f"queued {counts['QUEUED']}, running {counts['RUNNING']}, "
                f"blocked {counts['BLOCKED']}. LLM disabled; no live orders.")
    task_map = {"/scan": "scan", "/fundamental": "fundamental",
                "/catalyst": "catalyst", "/risk": "risk", "/learning": "learning"}
    if verb in task_map and len(command) == 1:
        job_id = queue.submit(task_map[verb])
        return f"Queued {task_map[verb]} research job: {job_id}. Not a trade signal."
    if verb == "/job" and len(command) == 2:
        job_id = command[1]
        if len(job_id) != 32 or any(c not in "0123456789abcdef" for c in job_id):
            return "Invalid job id."
        result = queue.status(job_id)
        return ("Not found." if not result else
                f"Job {job_id}: {result['state']} ({result['role']}); "
                "inspect source evidence locally.")
    return "Unsupported command. Allowed: /status /scan /fundamental /catalyst /risk /learning /job."


def send_if_opted_in(message: str, *, chat_id: str, transport=None) -> dict:
    """No retry, require an exact allowed chat and explicit enable switch."""
    if os.environ.get("MERIDYEN_TELEGRAM_SEND_ENABLED") != "true":
        return {"sent": False, "reason": "TELEGRAM_DISABLED"}
    token = os.environ.get("MERIDYEN_TELEGRAM_BOT_TOKEN", "")
    allowed = os.environ.get("MERIDYEN_TELEGRAM_ALLOWED_CHAT_ID", "")
    if not token or not allowed or str(chat_id) != allowed:
        return {"sent": False, "reason": "TELEGRAM_CREDENTIAL_OR_CHAT_NOT_VERIFIED"}
    if not isinstance(message, str) or len(message) > 4096 or not message:
        return {"sent": False, "reason": "INVALID_MESSAGE"}
    uri = f"https://api.telegram.org/bot{token}/sendMessage"
    body = json.dumps({"chat_id": allowed, "text": message,
                       "disable_web_page_preview": True}).encode()
    if transport is not None:
        result = transport(uri, body)
    else:
        try:
            req = urllib.request.Request(uri, data=body, headers={
                "Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read(64_000))
        except Exception:
            # Never log provider URL; Telegram embeds bot token in its path.
            return {"sent": False, "reason": "TELEGRAM_NETWORK_FAILURE"}
    if not isinstance(result, dict) or result.get("ok") is not True:
        return {"sent": False, "reason": "TELEGRAM_REJECTED"}
    return {"sent": True, "reason": "DELIVERY_ACKNOWLEDGED"}
