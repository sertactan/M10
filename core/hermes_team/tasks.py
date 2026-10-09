"""Durable local-only deterministic Hermes team queue; zero remote inference."""
from __future__ import annotations
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from core.hermes_team.evidence_workflows import perform_local_evidence_task
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
            db.execute("""CREATE TABLE IF NOT EXISTS handoffs(
                parent TEXT NOT NULL, child TEXT NOT NULL, task TEXT NOT NULL,
                PRIMARY KEY(parent,task))""")
            db.execute("""CREATE TABLE IF NOT EXISTS audit_events(
                id INTEGER PRIMARY KEY, job_id TEXT NOT NULL, state TEXT NOT NULL,
                recorded REAL NOT NULL)""")

    @contextmanager
    def _db(self):
        db = sqlite3.connect(str(self.path), timeout=3)
        try:
            with db:
                yield db
        finally:
            db.close()

    def submit(self, task: str, payload: dict | None = None) -> str:
        decision = route(task)
        if decision.get("status") == "INCONCLUSIVE":
            raise ValueError("UNKNOWN_TASK")
        if payload and (not isinstance(payload, dict) or len(json.dumps(payload)) > 4096):
            raise ValueError("INVALID_PAYLOAD")
        if payload and any(secret in json.dumps(payload).lower() for secret in
                           ('api_key', 'password', 'secret', 'authorization', 'token')):
            raise ValueError("SECRET_IN_PAYLOAD_BLOCKED")
        job_id = uuid.uuid4().hex
        now = time.time()
        with self._db() as db:
            db.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)",
                       (job_id, task, decision["role"], "QUEUED",
                        json.dumps(payload or {}), None, now, now, 0))
            db.execute("INSERT INTO audit_events(job_id,state,recorded) VALUES (?,?,?)",
                       (job_id, "QUEUED", now))
        return job_id

    def claim(self):
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            # System-wide single worker: an interrupted RUNNING job must
            # be reviewed before dispatching another job, even if stale.
            if db.execute("SELECT 1 FROM jobs WHERE state='RUNNING' LIMIT 1").fetchone():
                return None
            # An interrupted RUNNING job requires explicit operator review.
            # No automatic retry, thereby avoiding uncontrolled repeated effects.
            row = db.execute("SELECT id,task,payload,role FROM jobs WHERE state='QUEUED' ORDER BY created,id LIMIT 1").fetchone()
            if not row:
                return None
            db.execute("UPDATE jobs SET state='RUNNING',attempts=attempts+1,updated=? WHERE id=?",
                       (time.time(), row[0]))
            db.execute("INSERT INTO audit_events(job_id,state,recorded) VALUES(?,?,?)",
                       (row[0], "RUNNING", time.time()))
            return {"id": row[0], "task": row[1], "payload": json.loads(row[2]), "role": row[3]}

    def finish(self, job_id: str, result: dict, *, failed: bool = False):
        with self._db() as db:
            changed = db.execute(
                "UPDATE jobs SET state=?,result=?,updated=? WHERE id=? AND state='RUNNING'",
                ("BLOCKED" if failed else "DONE", json.dumps(result), time.time(), job_id),
            ).rowcount
        if changed != 1:
            raise ValueError("JOB_NOT_RUNNING")
        with self._db() as db:
            db.execute("INSERT INTO audit_events(job_id,state,recorded) VALUES(?,?,?)",
                       (job_id, "BLOCKED" if failed else "DONE", time.time()))

    def handoff(self, parent_id: str, child_task: str) -> str:
        """Idempotent explicit A1->specialist transfer; no LLM involved."""
        if child_task not in ("scan", "fundamental", "catalyst", "risk", "learning"):
            raise ValueError("CHILD_TASK_NOT_ALLOWED")
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            parent = db.execute("SELECT role,state FROM jobs WHERE id=?", (parent_id,)).fetchone()
            if parent is None or parent[0] != "A1" or parent[1] != "DONE":
                raise ValueError("PARENT_NOT_COMPLETE_CHIEF")
            row = db.execute("SELECT child FROM handoffs WHERE parent=? AND task=?",
                             (parent_id, child_task)).fetchone()
            if row:
                return row[0]
            child = uuid.uuid4().hex
            now = time.time()
            role = route(child_task)["role"]
            db.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)",
                       (child, child_task, role, "QUEUED", "{}", None, now, now, 0))
            db.execute("INSERT INTO handoffs VALUES(?,?,?)",
                       (parent_id, child, child_task))
            db.execute("INSERT INTO audit_events(job_id,state,recorded) VALUES(?,?,?)",
                       (child, "QUEUED", now))
            return child

    def review_interrupted(self, job_id: str) -> bool:
        """Operator action: block an abandoned task without replaying it."""
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            n = db.execute("UPDATE jobs SET state='BLOCKED', updated=? WHERE id=? AND state='RUNNING'",
                           (time.time(), job_id)).rowcount
            if n:
                db.execute("INSERT INTO audit_events(job_id,state,recorded) VALUES(?,?,?)",
                           (job_id, "BLOCKED_OPERATOR_REVIEW", time.time()))
        return n == 1

    def status(self, job_id: str):
        with self._db() as db:
            row = db.execute("SELECT id,task,role,state,result,attempts FROM jobs WHERE id=?",
                             (job_id,)).fetchone()
        return dict(zip(("id", "task", "role", "state", "result", "attempts"), row)) if row else None

    def summary(self) -> dict:
        """Only aggregate task counts; no source evidence or private payloads."""
        with self._db() as db:
            counts = dict(db.execute(
                "SELECT state, count(*) FROM jobs GROUP BY state").fetchall())
        return {"QUEUED": counts.get("QUEUED", 0),
                "RUNNING": counts.get("RUNNING", 0),
                "DONE": counts.get("DONE", 0),
                "BLOCKED": counts.get("BLOCKED", 0)}

    def dispatch_one(self):
        job = self.claim()
        if job is None:
            return None
        try:
            result = perform_local_evidence_task(job["task"])
        except Exception:
            result = {"status": "INCONCLUSIVE", "reason": "UNEXPECTED_LOCAL_AUDIT_FAILURE",
                      "llm_called": False}
        result = {"role": job["role"], "task": job["task"], **result}
        self.finish(job["id"], result, failed=result["status"] not in
                    ("DONE", "INCONCLUSIVE", "SEC_FILING_ISSUER_LINKS_REVIEWED_127_CANDIDATES_EVENT_TRIAGED_NOT_HISTORICAL_PIT"))
        return {"job_id": job["id"], **result}
