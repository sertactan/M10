"""Durable local-only deterministic Hermes team queue; zero remote inference."""
from __future__ import annotations
import json
import sqlite3
import time
import uuid
from pathlib import Path
from core.hermes_team.roles import route


class LocalTasks:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS jobs(
              id TEXT PRIMARY KEY, task TEXT NOT NULL, role TEXT NOT NULL,
              state TEXT NOT NULL, payload TEXT NOT NULL, result TEXT,
              created REAL NOT NULL, updated REAL NOT NULL, attempts INTEGER NOT NULL)""")

    def _db(self):
        return sqlite3.connect(str(self.path), timeout=3)

    def submit(self, task: str, payload: dict | None = None) -> str:
        decision = route(task)
        if decision.get("status") == "INCONCLUSIVE":
            raise ValueError("UNKNOWN_TASK")
        if payload and (not isinstance(payload, dict) or len(json.dumps(payload)) > 4096):
            raise ValueError("INVALID_PAYLOAD")
        job_id = uuid.uuid4().hex
        now = time.time()
        with self._db() as db:
            db.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)",
                       (job_id, task, decision["role"], "QUEUED",
                        json.dumps(payload or {}), None, now, now, 0))
        return job_id

    def claim(self):
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            # An interrupted RUNNING job requires explicit operator review.
            # No automatic retry, thereby avoiding uncontrolled repeated effects.
            row = db.execute("SELECT id,task,payload,role FROM jobs WHERE state='QUEUED' ORDER BY created,id LIMIT 1").fetchone()
            if not row:
                return None
            db.execute("UPDATE jobs SET state='RUNNING',attempts=attempts+1,updated=? WHERE id=?",
                       (time.time(), row[0]))
            return {"id": row[0], "task": row[1], "payload": json.loads(row[2]), "role": row[3]}

    def finish(self, job_id: str, result: dict, *, failed: bool = False):
        with self._db() as db:
            changed = db.execute(
                "UPDATE jobs SET state=?,result=?,updated=? WHERE id=? AND state='RUNNING'",
                ("BLOCKED" if failed else "DONE", json.dumps(result), time.time(), job_id),
            ).rowcount
        if changed != 1:
            raise ValueError("JOB_NOT_RUNNING")

    def status(self, job_id: str):
        with self._db() as db:
            row = db.execute("SELECT id,task,role,state,result,attempts FROM jobs WHERE id=?",
                             (job_id,)).fetchone()
        return dict(zip(("id", "task", "role", "state", "result", "attempts"), row)) if row else None

    def dispatch_one(self):
        job = self.claim()
        if job is None:
            return None
        # No operational price/SEC data assumed, no LLM calls, no trade side effects.
        result = {"status": "INCONCLUSIVE", "reason": "SOURCE_EVIDENCE_REQUIRED",
                  "role": job["role"], "task": job["task"], "llm_called": False}
        self.finish(job["id"], result)
        return {"job_id": job["id"], **result}
