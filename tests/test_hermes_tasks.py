from core.hermes_team.tasks import LocalTasks

def test_jobs_persist_fail_closed(tmp_path, monkeypatch):
    from core.hermes_team import tasks
    monkeypatch.setattr(tasks, "perform_local_evidence_task",
                        lambda task: {"status": "INCONCLUSIVE", "llm_called": False})
    db = tmp_path / "tasks.sqlite3"
    q = LocalTasks(db)
    job = q.submit("scan")
    assert LocalTasks(db).status(job)["state"] == "QUEUED"
    got = LocalTasks(db).dispatch_one()
    assert got["status"] == "INCONCLUSIVE"
    assert LocalTasks(db).status(job)["state"] == "DONE"
    assert q.dispatch_one() is None

def test_crash_does_not_automatically_retry(tmp_path):
    db = tmp_path / "tasks.sqlite3"
    q = LocalTasks(db)
    job = q.submit("risk")
    assert q.claim()["id"] == job
    assert LocalTasks(db).dispatch_one() is None
    assert LocalTasks(db).status(job)["state"] == "RUNNING"
