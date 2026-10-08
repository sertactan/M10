from __future__ import annotations

import json
from pathlib import Path
import sqlite3

from scripts.phase18_storage_readiness import inspect, _sqlite_probe, _price_files


def test_missing_runtime_does_not_create_database_or_require_drive(tmp_path):
    result=inspect(runtime_root=tmp_path)
    assert result["status"]=="LOCAL_ACTIVATION_EVIDENCE_REQUIRED"
    assert result["drive"]["required_for_database_queries"] is False
    assert result["drive"]["recommended_role"]=="OPTIONAL_ENCRYPTED_OFFSITE_BACKUP"
    assert result["market_database"]["present"] is False
    assert result["learning_database"]["present"] is False
    assert "PHASE13_WF9_PREFLIGHT_BLOCKED" in result["blockers"]
    assert not (tmp_path/"data/runtime/operational.db").exists()
    assert not (tmp_path/"data/runtime/meridyen_learning.sqlite3").exists()


def test_wrong_sqlite_schema_cannot_appear_production_ready(tmp_path):
    runtime=tmp_path/"M10"
    home=runtime/"data/runtime"
    home.mkdir(parents=True)
    con=sqlite3.connect(home/"operational.db")
    con.execute("CREATE TABLE irrelevant(x INTEGER)")
    con.commit()
    con.close()
    report=inspect(runtime_root=runtime)
    assert report["market_database"]["quick_check"]=="ok"
    assert report["status"]=="LOCAL_ACTIVATION_EVIDENCE_REQUIRED"
    assert report["phase13"]["status"]=="BLOCKED_SCHEMA"
    assert "PHASE14_DATASET_PIT_INPUT_AUDIT_BLOCKED" in report["blockers"]


def test_local_parquet_inventory_does_not_certify_price_data(tmp_path):
    folder=tmp_path/"parquet"
    folder.mkdir()
    (folder/"year_2020.parquet").write_bytes(b"fixture bytes not verified bars")
    (folder/"readme.txt").write_text("metadata")
    result=_price_files(folder)
    assert result["parquet_files"]==1
    assert result["non_parquet_files"]==1
    assert result["inventory_complete"] is True
    assert result["total_bytes"]>0
    report=inspect(runtime_root=tmp_path,parquet=folder)
    assert report["pit_independently_certified"] is False
    assert report["wf9_production_activated"] is False


def test_bounded_inventory_refuses_full_coverage_claim(tmp_path):
    folder=tmp_path/"parquet"
    folder.mkdir()
    for n in range(3):
        (folder/f"{n}.parquet").write_bytes(b"fake")
    assert _price_files(folder,max_files=1)["inventory_complete"] is False


def test_symlink_not_accepted_as_authoritative_data(tmp_path):
    folder=tmp_path/"parquet"
    folder.mkdir()
    outside=tmp_path/"outside.parquet"
    outside.write_bytes(b"untrusted")
    (folder/"linked.parquet").symlink_to(outside)
    result=_price_files(folder)
    assert result["unsafe_symlinks"]==1
    assert result["inventory_complete"] is True
    report=inspect(runtime_root=tmp_path,parquet=folder)
    assert "PRICE_FILE_INVENTORY_NOT_COMPLETE" in report["blockers"]


def test_corrupt_database_is_never_updated_by_probe(tmp_path):
    p=tmp_path/"operational.db"
    p.write_bytes(b"invalid sqlite bytes")
    original=p.read_bytes()
    state=_sqlite_probe(p)
    assert state["quick_check"].startswith("ERROR_")
    assert p.read_bytes()==original
