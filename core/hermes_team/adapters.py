"""Payload-only adapters. No Telegram/network side effects unless separately approved."""
from __future__ import annotations

from urllib.parse import urlencode


def telegram_message(report: dict) -> str:
    if report.get("schema") != "MERIDYEN_HERMES_FINANCIAL_V1":
        raise ValueError("INVALID_REPORT")
    symbol = report.get("symbol") or "UNKNOWN"
    if not symbol.isalnum() or len(symbol) > 12:
        raise ValueError("INVALID_SYMBOL")
    status = report.get("s16_c_status")
    canonical = str(report["s16_c"]) if status == "CANONICAL" else "INCONCLUSIVE"
    return (f"Meridyen: {symbol}\nPrice: {report.get('price') or 'N/A'}\n"
            f"As-of: {report.get('price_timestamp') or 'UNKNOWN'}\n"
            f"S16-E: {report.get('s16_e') if report.get('s16_e') is not None else 'N/A'}\n"
            f"S16-C: {canonical}\nDecision: {report.get('decision')}\n"
            "RESEARCH ONLY. No live trades.")


def plugin_response(report: dict) -> dict:
    if report.get("schema") != "MERIDYEN_HERMES_FINANCIAL_V1":
        raise ValueError("INVALID_REPORT")
    # Pure dict for existing Private Plugin transport; does not advertise a
    # nonexistent remote command or claim a connected plugin.
    return {"schema": report["schema"], "status": report["decision"],
            "result": report, "transport_connected": False}


def telegram_request(token: str, chat_id: str, message: str) -> tuple[str, bytes]:
    """Construct but do not transmit an opt-in Telegram Bot API request."""
    if not token or not chat_id or not message:
        raise ValueError("TELEGRAM_NOT_CONFIGURED")
    if len(message) > 4096 or any(c in chat_id for c in "\r\n"):
        raise ValueError("INVALID_TELEGRAM_PAYLOAD")
    return ("https://api.telegram.org/bot" + token + "/sendMessage",
            urlencode({"chat_id": chat_id, "text": message}).encode("utf-8"))
