from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from data.database.sqlite_store import SQLiteStore


@dataclass(frozen=True)
class BackgroundSyncTask:
    task_id: str
    task_type: str
    dedupe_key: str
    payload: dict[str, Any]
    priority: int
    status: str
    attempts: int
    max_attempts: int
    run_after: datetime
    last_error: str | None


class BackgroundSyncRepository:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _iso(value: datetime) -> str:
        if value.tzinfo is None:
            raise ValueError("background sync timestamps must be timezone-aware")
        return value.astimezone(timezone.utc).isoformat()

    def enqueue(
        self,
        task_type: str,
        dedupe_key: str,
        payload: dict[str, Any],
        *,
        priority: int = 100,
        max_attempts: int = 3,
        run_after: datetime | None = None,
    ) -> str:
        existing = self.store.connection.execute(
            """
            SELECT task_id
            FROM background_sync_tasks
            WHERE task_type=? AND dedupe_key=?
            LIMIT 1
            """,
            (task_type, dedupe_key),
        ).fetchone()
        if existing is not None:
            return str(existing["task_id"])

        now = self._now()
        task_id = str(uuid.uuid4())
        self.store.connection.execute(
            """
            INSERT INTO background_sync_tasks (
                task_id,task_type,dedupe_key,payload_json,priority,status,
                attempts,max_attempts,run_after,created_at,updated_at
            ) VALUES (?,?,?,?,?,'PENDING',0,?,?,?,?,?)
            """,
            (
                task_id,
                task_type,
                dedupe_key,
                json.dumps(payload, sort_keys=True),
                int(priority),
                int(max_attempts),
                self._iso(run_after or now),
                self._iso(now),
                self._iso(now),
            ),
        )
        self.store.connection.commit()
        return task_id

    def claim_ready(self, *, limit: int = 8) -> list[BackgroundSyncTask]:
        now = self._now()
        rows = self.store.connection.execute(
            """
            SELECT *
            FROM background_sync_tasks
            WHERE status IN ('PENDING','RETRY')
              AND run_after<=?
            ORDER BY priority ASC, created_at ASC
            LIMIT ?
            """,
            (self._iso(now), int(limit)),
        ).fetchall()

        out: list[BackgroundSyncTask] = []
        for row in rows:
            attempts = int(row["attempts"]) + 1
            self.store.connection.execute(
                """
                UPDATE background_sync_tasks
                SET status='RUNNING', attempts=?, started_at=?, updated_at=?
                WHERE task_id=?
                """,
                (attempts, self._iso(now), self._iso(now), row["task_id"]),
            )
            out.append(
                BackgroundSyncTask(
                    task_id=str(row["task_id"]),
                    task_type=str(row["task_type"]),
                    dedupe_key=str(row["dedupe_key"]),
                    payload=json.loads(row["payload_json"]),
                    priority=int(row["priority"]),
                    status="RUNNING",
                    attempts=attempts,
                    max_attempts=int(row["max_attempts"]),
                    run_after=datetime.fromisoformat(row["run_after"]),
                    last_error=row["last_error"],
                )
            )
        self.store.connection.commit()
        return out

    def mark_success(self, task_id: str) -> None:
        now = self._now()
        self.store.connection.execute(
            """
            UPDATE background_sync_tasks
            SET status='SUCCEEDED', completed_at=?, updated_at=?, last_error=NULL
            WHERE task_id=?
            """,
            (self._iso(now), self._iso(now), task_id),
        )
        self.store.connection.commit()

    def mark_failure(self, task: BackgroundSyncTask, error: str, *, retry_delay_seconds: int) -> str:
        now = self._now()
        if task.attempts >= task.max_attempts:
            status = "FAILED"
            run_after = task.run_after
            completed_at = self._iso(now)
        else:
            status = "RETRY"
            run_after = now + timedelta(seconds=max(0, int(retry_delay_seconds)))
            completed_at = None

        self.store.connection.execute(
            """
            UPDATE background_sync_tasks
            SET status=?, run_after=?, last_error=?, completed_at=?, updated_at=?
            WHERE task_id=?
            """,
            (
                status,
                self._iso(run_after),
                error[:1000],
                completed_at,
                self._iso(now),
                task.task_id,
            ),
        )
        self.store.connection.commit()
        return status

    def counts(self) -> dict[str, int]:
        rows = self.store.connection.execute(
            """
            SELECT status,COUNT(*) AS n
            FROM background_sync_tasks
            GROUP BY status
            """
        ).fetchall()
        return {str(row["status"]): int(row["n"]) for row in rows}
