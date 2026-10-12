"""Isolated SQLite sidecar; immutable snapshots, no production DB writes."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager, closing
from pathlib import Path

from .contracts import digest


class EvidenceStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.is_symlink():
            raise ValueError("Refusing symlinked personal sidecar")
        with self._open() as con:
            con.execute("""CREATE TABLE IF NOT EXISTS personal_runs(
                run_id TEXT PRIMARY KEY, ticker TEXT NOT NULL, cik TEXT,
                fiscal_period TEXT, created_at TEXT NOT NULL, payload TEXT NOT NULL,
                receipt_sha256 TEXT NOT NULL, provider TEXT, prompt_version TEXT,
                code_commit TEXT, scenario_version TEXT,
                review_status TEXT NOT NULL DEFAULT 'NOT_EXPERT_REVIEWED')""")

    @contextmanager
    def _open(self):
        # sqlite3.Connection.__exit__ commits but does not close its file
        # handle. Closing is essential for Windows rename/delete and smoke tests.
        with closing(sqlite3.connect(str(self.path), timeout=10)) as con:
            with con:
                yield con

    def save(self, result: dict):
        if result.get("canonical_accepted") is not False:
            raise ValueError("Original/canonical result is prohibited in sidecar")
        sha = digest({k: v for k, v in result.items() if k != "receipt_sha256"})
        if result.get("receipt_sha256") != sha:
            raise ValueError("Personal receipt checksum mismatch")
        run_id = result["run_id"]
        data = json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False)
        with self._open() as con:
            con.execute("""INSERT INTO personal_runs
                (run_id,ticker,cik,fiscal_period,created_at,payload,receipt_sha256,
                 provider,prompt_version,code_commit,scenario_version,review_status)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""", (
                    run_id, result["ticker"], result.get("cik"),
                    result.get("period_end"), result["created_at"], data, sha,
                    result.get("llm_provider", "OFFLINE"), result.get("prompt_version", "V1"),
                    result.get("code_commit"), result.get("scenario_version", "V1"),
                    result.get("user_review_status", "NOT_EXPERT_REVIEWED"),
                ))
        return sha

    def latest(self, ticker: str) -> dict | None:
        with self._open() as con:
            row = con.execute(
                "SELECT payload,receipt_sha256 FROM personal_runs WHERE ticker=? ORDER BY created_at DESC,run_id DESC LIMIT 1",
                (ticker.upper(),)).fetchone()
        if row is None:
            return None
        payload = json.loads(row[0])
        if digest({k: v for k, v in payload.items() if k != "receipt_sha256"}) != row[1]:
            raise ValueError("Sidecar receipt corrupted")
        return payload
