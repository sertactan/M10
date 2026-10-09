"""Persistent, fail-closed one-call-at-a-time FREE model request guard.

Not a remote provider quota verifier or a cloud billing enforcement service.
Only a private, authenticated local proxy may call this module.
"""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


class Blocked(RuntimeError):
    pass


@dataclass(frozen=True)
class Policy:
    enabled: bool = False
    provider: str = ""
    model: str = ""
    free_tier_verified: bool = False
    nonbillable_account_verified: bool = False
    verification_expires_epoch: int = 0
    daily_request_cap: int = 0
    minute_request_cap: int = 0
    max_prompt_bytes: int = 4096
    max_output_tokens: int = 512

    def validate(self, now: float) -> None:
        if not self.enabled:
            raise Blocked("GATE_DISABLED")
        if self.provider not in ("gemini", "openrouter"):
            raise Blocked("UNKNOWN_PROVIDER")
        if not self.model or self.model.strip() != self.model:
            raise Blocked("MODEL_NOT_PINNED")
        if self.provider == "openrouter" and not self.model.endswith(":free"):
            raise Blocked("OPENROUTER_NOT_FREE_VARIANT")
        if not self.free_tier_verified or not self.nonbillable_account_verified:
            raise Blocked("FREE_ACCOUNT_UNVERIFIED")
        if self.verification_expires_epoch <= now:
            raise Blocked("VERIFICATION_EXPIRED")
        if not (0 < self.daily_request_cap <= 1000 and 0 < self.minute_request_cap <= 100):
            raise Blocked("INVALID_REQUEST_CAP")
        if not (0 < self.max_prompt_bytes <= 65536 and 0 < self.max_output_tokens <= 8192):
            raise Blocked("INVALID_TOKEN_POLICY")


class QuotaGuard:
    def __init__(self, path: Path):
        self.path = Path(path)

    def _connect(self):
        # Caller supplies a private local data directory, never shared with Git.
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(str(self.path), timeout=3, isolation_level=None)
        db.execute("PRAGMA busy_timeout=3000")
        db.execute("""CREATE TABLE IF NOT EXISTS calls (
            id TEXT PRIMARY KEY, at_epoch REAL NOT NULL, provider TEXT NOT NULL,
            model TEXT NOT NULL, in_flight INTEGER NOT NULL, lease_until REAL NOT NULL
        )""")
        return db

    def reserve(self, *, request_id: str, policy: Policy, prompt_bytes: int,
                now: float | None = None) -> None:
        current = time.time() if now is None else now
        policy.validate(current)
        if not request_id or len(request_id) > 100:
            raise Blocked("INVALID_REQUEST_ID")
        if prompt_bytes < 1 or prompt_bytes > policy.max_prompt_bytes:
            raise Blocked("PROMPT_TOO_LARGE_OR_EMPTY")
        day = datetime.fromtimestamp(current, timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        ).timestamp()
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            # No second LLM may start while an existing lease is active.
            if db.execute("SELECT 1 FROM calls WHERE in_flight=1 AND lease_until>? LIMIT 1",
                          (current,)).fetchone():
                raise Blocked("ONE_LLM_AT_A_TIME")
            count_day = db.execute("SELECT count(*) FROM calls WHERE at_epoch>=? AND provider=?",
                                   (day, policy.provider)).fetchone()[0]
            count_minute = db.execute(
                "SELECT count(*) FROM calls WHERE at_epoch>? AND provider=?",
                (current - 60, policy.provider)
            ).fetchone()[0]
            if count_day >= policy.daily_request_cap or count_minute >= policy.minute_request_cap:
                raise Blocked("LOCAL_FREE_QUOTA_EXHAUSTED")
            try:
                db.execute("INSERT INTO calls VALUES (?,?,?,?,1,?)",
                           (request_id, current, policy.provider, policy.model, current + 90))
            except sqlite3.IntegrityError as exc:
                raise Blocked("DUPLICATE_REQUEST_ID") from exc
            db.commit()
        finally:
            db.close()

    def finish(self, request_id: str) -> None:
        db = self._connect()
        try:
            db.execute("UPDATE calls SET in_flight=0, lease_until=0 WHERE id=?", (request_id,))
            db.commit()
        finally:
            db.close()
