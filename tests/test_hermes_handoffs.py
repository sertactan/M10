from __future__ import annotations
import sqlite3
import pytest
from core.hermes_team.tasks import LocalTasks


def test_chief_handoffs_idempotent_and_durable(tmp_path, monkeypatch):
    from core.hermes_team import tasks
    monkeypatch.setattr(tasks, "perform_local_evidence_task",
                        lambda task: {"status": "INCONCLUSIVE", "llm_called": False})
    path = tmp_path / "q.sqlite3"
    q = LocalTasks(path)
    parent = q.submit("strategy")
    assert q.dispatch_one()["role"] == "A1"
    a2 = q.handoff(parent, "scan")
    a3 = q.handoff(parent, "fundamental")
    assert q.handoff(parent, "scan") == a2
    assert LocalTasks(path).status(a2)["role"] == "A2"
    assert q.dispatch_one()["role"] == "A2"
    assert q.dispatch_one()["role"] == "A3"
    assert q.status(a3)["attempts"] == 1
    assert q.summary()["DONE"] == 3
    with sqlite3.connect(path) as con:
        assert con.execute("SELECT COUNT(*) FROM handoffs").fetchone()[0] == 2


def test_interrupted_task_blocks_all_workers_until_review(tmp_path):
    path = tmp_path / "jobs.sqlite3"
    q = LocalTasks(path)
    a = q.submit("scan")
    b = q.submit("risk")
    assert q.claim()["id"] == a
    assert LocalTasks(path).claim() is None
    assert LocalTasks(path).review_interrupted(a) is True
    assert q.status(a)["state"] == "BLOCKED"
    assert q.claim()["id"] == b
    assert q.status(b)["attempts"] == 1


def test_no_secret_payload_in_persistent_task(tmp_path):
    q = LocalTasks(tmp_path / "db")
    with pytest.raises(ValueError, match="SECRET"):
        q.submit("strategy", {"api_key": "never-store"})
    with pytest.raises(ValueError, match="PARENT"):
        q.handoff(q.submit("strategy"), "scan")
