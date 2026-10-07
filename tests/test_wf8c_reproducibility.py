from __future__ import annotations

from datetime import datetime,timezone
from pathlib import Path

import pytest

from core.backtest.wf8_reproducibility import (
    WF8ReproducibilityError,
    WF8ReproducibilityManifestService,
)
from data.database.sqlite_store import SQLiteStore


NOW=datetime(2026,10,7,tzinfo=timezone.utc)


def _seed(store: SQLiteStore) -> None:
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
        ("F1","WF6",1,"2013-01-01","2023-12-31","2024-01-01","2024-12-31","COMPLETE",1,1,0,1,0,now,now),
    )
    store.connection.execute(
        "INSERT INTO security_master (security_id,ticker,name,exchange,market,active,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
        ("SEC","SEC","SEC","NASDAQ","US",1,now,now),
    )
    store.connection.execute(
        "INSERT INTO wf6_oos_observations (fold_id,source_observation_id,security_id,ticker,as_of_date,primary_route,v12_score,v12_status,v141_score,v141_status,outcome_status,fm252,outcome_class,repeated_security,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("F1","OBS","SEC","SEC","2024-01-31","F10",80,"READY",82,"READY","READY",10.5,"TRUE_10X",0,now),
    )
    store.connection.execute(
        "INSERT INTO wf7_validation_runs (run_id,wf6_run_id,model_version,validation_policy,status,created_at,completed_at) VALUES (?,?,?,?,?,?,?)",
        ("WF7","WF6","S15.3_V1.4.1","WF7_VALIDATION_POLICY_V1_2026-10-07","COMPLETE",now,now),
    )
    store.connection.execute(
        "INSERT INTO wf7_validation_summary (run_id,ready_oos_n,scored_ready_n,score_coverage_pct,true10_count,base_rate_10x_pct,pr_auc_average_precision,probability_head_status,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        ("WF7",1,1,100,1,100,100,"NOT_AVAILABLE_SCORE_IS_NOT_PROBABILITY",now),
    )
    for selector in ("SCORE_GE_65","SCORE_GE_75","SCORE_GE_80","SCORE_GE_85","TOP20","TOP50"):
        store.connection.execute(
            "INSERT INTO wf7_threshold_metrics (run_id,selector,threshold,selected_n,true10_n,created_at) VALUES (?,?,?,?,?,?)",
            ("WF7",selector,None,1,1,now),
        )
    buckets=(
        ("<55",0,55),("55-64",55,65),("65-74",65,75),
        ("75-79",75,80),("80-84",80,85),("85+",85,101),
    )
    for label,low,high in buckets:
        store.connection.execute(
            "INSERT INTO wf7_calibration_buckets (run_id,bucket_label,score_low,score_high,sample_size,true10_count,p2_plus_pct,p5_plus_pct,p7_plus_pct,p10_plus_pct,median_fm252,sample_quality,status,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("WF7",label,low,high,40,1,10,5,3,1,2,"REDUCED_SAMPLE","READY",now),
        )
    store.connection.execute(
        "INSERT INTO wf8_hardening_runs (hardening_id,wf5_run_id,wf6_run_id,wf7_run_id,policy_version,status,blockers_json,warnings_json,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        ("HARD","WF5","WF6","WF7","WF8_PRODUCTION_HARDENING_V1_2026-10-07","PRODUCTION_EVIDENCE_READY","[]","[]",now),
    )
    store.connection.execute(
        "INSERT INTO wf8_hardening_checks (hardening_id,check_name,passed,blocking,evidence,created_at) VALUES (?,?,?,?,?,?)",
        ("HARD","test",1,1,"ok",now),
    )
    store.connection.commit()


def test_manifest_is_deterministic_and_verifiable(tmp_path: Path) -> None:
    store=SQLiteStore(tmp_path/"manifest.sqlite"); store.initialize()
    try:
        _seed(store)
        service=WF8ReproducibilityManifestService(store)
        first=service.create(hardening_id="HARD",code_identity="commit-abc")
        second=service.compute(hardening_id="HARD",code_identity="commit-abc")
        assert first.chain_hash==second.chain_hash
        assert service.verify(first.manifest_id).chain_hash==first.chain_hash
    finally:
        store.close()


def test_manifest_detects_wf7_tampering(tmp_path: Path) -> None:
    store=SQLiteStore(tmp_path/"tamper.sqlite"); store.initialize()
    try:
        _seed(store)
        service=WF8ReproducibilityManifestService(store)
        manifest=service.create(hardening_id="HARD",code_identity="commit-abc")
        store.connection.execute(
            "UPDATE wf7_calibration_buckets SET p10_plus_pct=99 WHERE run_id='WF7' AND bucket_label='80-84'"
        )
        store.connection.commit()
        with pytest.raises(WF8ReproducibilityError,match="wf7_hash"):
            service.verify(manifest.manifest_id)
        row=store.connection.execute(
            "SELECT status FROM wf8_reproducibility_manifests WHERE manifest_id=?",
            (manifest.manifest_id,),
        ).fetchone()
        assert row["status"]=="TAMPERED"
    finally:
        store.close()


def test_manifest_requires_code_identity(tmp_path: Path) -> None:
    store=SQLiteStore(tmp_path/"identity.sqlite"); store.initialize()
    try:
        _seed(store)
        with pytest.raises(WF8ReproducibilityError,match="code_identity"):
            WF8ReproducibilityManifestService(store).compute(
                hardening_id="HARD",code_identity=""
            )
    finally:
        store.close()
