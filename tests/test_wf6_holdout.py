from datetime import date,datetime,timezone
from pathlib import Path

import pytest

from core.backtest.wf6_holdout import (
    HOLDOUT_POLICY_VERSION,
    WF6HoldoutRegistry,
)
from data.database.sqlite_store import SQLiteStore


def _store(tmp_path: Path):
    store=SQLiteStore(tmp_path/"wf6-holdout.sqlite"); store.initialize()
    store.connection.execute(
        """
        INSERT INTO wf5_replay_runs
        (run_id,start_date,end_date,frequency,v12_version,v141_version,status,created_at)
        VALUES (?,?,?,?,?,?,?,?)
        """,
        (
            "WF5","2013-01-01","2024-12-31","MONTHLY",
            "V12","V141","COMPLETE",datetime.now(timezone.utc).isoformat(),
        ),
    )
    store.connection.commit()
    return store


def test_holdout_lock_is_deterministic_and_immutable(tmp_path: Path) -> None:
    store=_store(tmp_path)
    try:
        reg=WF6HoldoutRegistry(store)
        a=reg.freeze(
            source_wf5_run_id="WF5",
            feature_version="FEATURES_V1",
            threshold_version="THRESHOLDS_V1",
        )
        b=reg.freeze(
            source_wf5_run_id="WF5",
            feature_version="FEATURES_V1",
            threshold_version="THRESHOLDS_V1",
        )
        assert a.lock_id==b.lock_id
        assert a.holdout_start==date(2024,1,1)
        assert a.holdout_end==date(2026,12,31)
        assert HOLDOUT_POLICY_VERSION=="WF6_HOLDOUT_POLICY_V1_2026-10-07"
        reg.open(a.lock_id)
        row=store.connection.execute(
            "SELECT * FROM wf6_holdout_locks WHERE lock_id=?",(a.lock_id,)
        ).fetchone()
        assert row["status"]=="OPENED"
        assert row["feature_version"]=="FEATURES_V1"
        assert row["threshold_version"]=="THRESHOLDS_V1"
    finally:
        store.close()


def test_holdout_requires_version_freeze(tmp_path: Path) -> None:
    store=_store(tmp_path)
    try:
        reg=WF6HoldoutRegistry(store)
        with pytest.raises(ValueError):
            reg.freeze(
                source_wf5_run_id="WF5",
                feature_version="",
                threshold_version="THRESHOLDS_V1",
            )
    finally:
        store.close()
