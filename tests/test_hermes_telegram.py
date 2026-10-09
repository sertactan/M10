from core.hermes_team.tasks import LocalTasks
from core.hermes_team.telegram_control import interpret_update, send_if_opted_in


def test_telegram_chat_allowlist_and_no_trades(tmp_path):
    q = LocalTasks(tmp_path / "jobs.db")
    msg = {"message": {"chat": {"id": 123}, "from": {"is_bot": False}, "text": "/scan"}}
    assert interpret_update(msg, allowed_chat="456", queue=q) is None
    result = interpret_update(msg, allowed_chat="123", queue=q)
    assert result.startswith("Queued scan")
    assert "trade" in result.lower()
    assert "Unsupported" in interpret_update(
        {"message": {"chat": {"id": 123}, "text": "/buy"}},
        allowed_chat="123", queue=q)


def test_telegram_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("MERIDYEN_TELEGRAM_SEND_ENABLED", raising=False)
    assert send_if_opted_in("x", chat_id="123") == {
        "sent": False, "reason": "TELEGRAM_DISABLED"}


def test_telegram_real_transport_contract_injected(monkeypatch):
    monkeypatch.setenv("MERIDYEN_TELEGRAM_SEND_ENABLED", "true")
    monkeypatch.setenv("MERIDYEN_TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("MERIDYEN_TELEGRAM_ALLOWED_CHAT_ID", "123")
    assert send_if_opted_in("research", chat_id="456")["sent"] is False
    assert send_if_opted_in("research", chat_id="123",
                            transport=lambda uri, body: {"ok": True})["sent"] is True
