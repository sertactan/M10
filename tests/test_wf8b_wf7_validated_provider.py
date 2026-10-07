from __future__ import annotations

from datetime import datetime,timezone
from pathlib import Path

import pytest

from core.forecast.calibration import ForecastCalibrationUnavailable
from core.forecast.wf7_validated_provider import (
    WF7ValidatedMagnitudeCalibrationProvider,
    score_bucket,
)
from data.database.sqlite_store import SQLiteStore


NOW=datetime(2026,10,7,23,59,tzinfo=timezone.utc)


def test_score_bucket_boundaries() -> None:
    assert score_bucket(54.9)[2]=="<55"
    assert score_bucket(55.0)[2]=="55-64"
    assert score_bucket(80.0)[2]=="80-84"
    assert score_bucket(85.0)[2]=="85+"


def _store(tmp_path: Path) -> SQLiteStore:
    store=SQLiteStore(tmp_path/"wf8b.sqlite")
    store.initialize()
    return store


def _seed_chain(store: SQLiteStore, *, bucket_n: int=40, bucket_status: str="READY") -> None:
    now=NOW.isoformat()
    store.connection.execute(
        "INSERT INTO wf5_replay_runs (run_id,start_date,end_date,frequency,v12_version,v141_version,status,created_at,completed_at) VALUES (?,?,?,?,?,?,?,?,?)",
        ("WF5","2013-01-01","2024-12-31","MONTHLY","V12","V141","COMPLETE",now,now),
    )
    store.connection.execute(
        "INSERT INTO wf6_walk_forward_runs (run_id,source_wf5_run_id,reference_start_year,first_test_year,last_test_year,v12_version,v141_version,leakage_policy,status,created_at,completed_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        ("WF6","WF5",2013,2018,2024,"V12","V141","WF6_LEAKAGE_POLICY_V1_2026-10-07","COMPLETE",now,now),
    )
    store.connection.execute(
        "INSERT INTO wf6_walk_forward_folds (fold_id,run_id,fold_index,reference_start_date,reference_end_date,test_start_date,test_end_date,status,oos_observations,ready_outcomes,censored_outcomes,v141_ready,same_security_overlap,created_at,completed_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("F1","WF6",1,"2013-01-01","2023-12-31","2024-01-01","2024-12-31","COMPLETE",100,90,10,80,0,now,now),
    )
    store.connection.execute(
        "INSERT INTO wf7_validation_runs (run_id,wf6_run_id,model_version,validation_policy,status,created_at,completed_at) VALUES (?,?,?,?,?,?,?)",
        ("WF7","WF6","S15.3_V1.4.1","WF7_VALIDATION_POLICY_V1_2026-10-07","COMPLETE",now,now),
    )
    store.connection.execute(
        "INSERT INTO wf7_calibration_buckets (run_id,bucket_label,score_low,score_high,sample_size,true10_count,p2_plus_pct,p5_plus_pct,p7_plus_pct,p10_plus_pct,median_fm252,sample_quality,status,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("WF7","80-84",80,85,bucket_n,2,20.0,8.0,4.0,2.0,2.2,"NORMAL" if bucket_n>=50 else "REDUCED_SAMPLE",bucket_status,now),
    )
    store.connection.execute(
        "INSERT INTO wf8_hardening_runs (hardening_id,wf5_run_id,wf6_run_id,wf7_run_id,policy_version,status,blockers_json,warnings_json,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        ("HARD","WF5","WF6","WF7","WF8_PRODUCTION_HARDENING_V1_2026-10-07","PRODUCTION_EVIDENCE_READY","[]","[]",now),
    )
    store.connection.commit()


def test_provider_uses_only_hardened_wf7_bucket(tmp_path: Path) -> None:
    store=_store(tmp_path)
    try:
        _seed_chain(store,bucket_n=40)
        c=WF7ValidatedMagnitudeCalibrationProvider(store).calibrate(score=82,as_of=NOW)
        assert c.bucket_label=="80-84"
        assert c.sample_size==40
        assert c.probability_2x_plus_pct==20.0
        assert c.probability_10x_plus_pct==2.0
        assert c.hardening_id=="HARD"
    finally:
        store.close()


def test_provider_fails_closed_when_bucket_under_30(tmp_path: Path) -> None:
    store=_store(tmp_path)
    try:
        _seed_chain(store,bucket_n=20,bucket_status="INCONCLUSIVE_N_LT_30")
        with pytest.raises(ForecastCalibrationUnavailable):
            WF7ValidatedMagnitudeCalibrationProvider(store).calibrate(score=82,as_of=NOW)
    finally:
        store.close()
