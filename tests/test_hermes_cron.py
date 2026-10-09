from pathlib import Path
from scripts.hermes_team_no_agent_tick import main


def test_cron_no_pending_is_silent(monkeypatch, capsys):
    from scripts import hermes_team_no_agent_tick as cron
    class FakeResult:
        returncode = 0
        stdout = '{"status":"NO_PENDING_WORK"}'
    monkeypatch.setattr(cron.subprocess, "run", lambda *a, **k: FakeResult())
    monkeypatch.setattr(Path, "is_file", lambda self: True)
    assert main() == 0
    assert capsys.readouterr().out == ""
