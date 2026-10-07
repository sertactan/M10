from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone

from core.backtest.wf6_policy import LEAKAGE_POLICY_VERSION
from core.models.s153_v12 import S153V12Model
from core.models.s153_v141 import S153V141Model


HOLDOUT_POLICY_VERSION = "WF6_HOLDOUT_POLICY_V1_2026-10-07"


@dataclass(frozen=True)
class HoldoutLock:
    lock_id: str
    source_wf5_run_id: str
    holdout_start: date
    holdout_end: date
    v12_version: str
    v141_version: str
    feature_version: str
    threshold_version: str
    dataset_identity_hash: str
    status: str


def _identity(payload: dict) -> str:
    raw=json.dumps(payload,sort_keys=True,separators=(",",":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class WF6HoldoutRegistry:
    """Immutable freeze/open registry for the final holdout.

    Opening a holdout never mutates its frozen model/feature/threshold identity.
    Any changed identity requires a new lock_id and therefore a new evaluation.
    """

    def __init__(self, store) -> None:
        self.store=store

    def freeze(
        self,
        *,
        source_wf5_run_id: str,
        feature_version: str,
        threshold_version: str,
        holdout_start: date=date(2024,1,1),
        holdout_end: date=date(2026,12,31),
    ) -> HoldoutLock:
        if holdout_end < holdout_start:
            raise ValueError("holdout_end must be >= holdout_start")
        source=self.store.connection.execute(
            "SELECT * FROM wf5_replay_runs WHERE run_id=?",
            (source_wf5_run_id,),
        ).fetchone()
        if source is None:
            raise ValueError("unknown WF5 replay run")
        if not feature_version.strip() or not threshold_version.strip():
            raise ValueError("feature_version and threshold_version are required")

        payload={
            "source_wf5_run_id":source_wf5_run_id,
            "holdout_start":holdout_start.isoformat(),
            "holdout_end":holdout_end.isoformat(),
            "v12_version":S153V12Model.canonical_formula_version,
            "v141_version":S153V141Model.canonical_formula_version,
            "feature_version":feature_version,
            "threshold_version":threshold_version,
            "leakage_policy":LEAKAGE_POLICY_VERSION,
            "holdout_policy":HOLDOUT_POLICY_VERSION,
        }
        digest=_identity(payload)
        lock_id=str(uuid.uuid5(uuid.NAMESPACE_URL,digest))
        now=datetime.now(timezone.utc).isoformat()
        self.store.connection.execute(
            """
            INSERT INTO wf6_holdout_locks (
                lock_id,source_wf5_run_id,holdout_start,holdout_end,
                v12_version,v141_version,feature_version,threshold_version,
                leakage_policy,holdout_policy,dataset_identity_hash,status,frozen_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(lock_id) DO NOTHING
            """,
            (
                lock_id,source_wf5_run_id,holdout_start.isoformat(),holdout_end.isoformat(),
                payload["v12_version"],payload["v141_version"],feature_version,
                threshold_version,LEAKAGE_POLICY_VERSION,HOLDOUT_POLICY_VERSION,
                digest,"FROZEN",now,
            ),
        )
        self.store.connection.commit()
        return HoldoutLock(
            lock_id=lock_id,source_wf5_run_id=source_wf5_run_id,
            holdout_start=holdout_start,holdout_end=holdout_end,
            v12_version=payload["v12_version"],v141_version=payload["v141_version"],
            feature_version=feature_version,threshold_version=threshold_version,
            dataset_identity_hash=digest,status="FROZEN",
        )

    def open(self, lock_id: str) -> None:
        row=self.store.connection.execute(
            "SELECT status FROM wf6_holdout_locks WHERE lock_id=?",
            (lock_id,),
        ).fetchone()
        if row is None:
            raise ValueError("unknown holdout lock")
        if str(row["status"])=="OPENED":
            return
        self.store.connection.execute(
            """
            UPDATE wf6_holdout_locks
            SET status='OPENED',opened_at=?
            WHERE lock_id=? AND status='FROZEN'
            """,
            (datetime.now(timezone.utc).isoformat(),lock_id),
        )
        self.store.connection.commit()
