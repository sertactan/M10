from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess

import pytest
from core.learning_v2.journal import backup,connect
from core.learning_v2.recovery import read_manifest,restore_snapshot,verify_snapshot
from scripts.phase16_learning_cycle import cycle
from scripts.sync_learning_backup import (
    prepare,validate_crypt_remote,upload_verified,download_verified,
    recover_from_cloud_manifest
)


def _backup(tmp_path: Path):
    db=tmp_path/"learning.sqlite3"
    conn=connect(db)
    conn.execute("INSERT INTO learning_v2_feedback (category,note,source_ref,created_at) VALUES (?,?,?,?)",
                 ("QUALITY","example","test-evidence","2026-10-08T00:00:00Z"))
    conn.commit()
    conn.close()
    return db,backup(db,tmp_path/"backups")


def test_backup_unique_even_within_one_second(tmp_path):
    db,first=_backup(tmp_path)
    second=backup(db,tmp_path/"backups")
    assert first["file"]!=second["file"]
    assert Path(first["file"]).exists() and Path(second["file"]).exists()


def test_recovery_restores_to_fresh_database_without_overwriting(tmp_path):
    db,meta=_backup(tmp_path)
    manifest=Path(meta["manifest_file"])
    result=restore_snapshot(manifest,tmp_path/"restored.sqlite3")
    assert result["status"]=="RESTORED_NEW_DB_ONLY"
    con=sqlite3.connect(tmp_path/"restored.sqlite3")
    assert con.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
    assert con.execute("SELECT COUNT(*) FROM learning_v2_feedback").fetchone()[0]==1
    con.close()
    with pytest.raises(ValueError,match="already exists"):
        restore_snapshot(manifest,tmp_path/"restored.sqlite3")
    assert db.exists()


def test_tampered_snapshot_rejected_before_destination(tmp_path):
    _,meta=_backup(tmp_path)
    Path(meta["file"]).write_bytes(b"tampered")
    dest=tmp_path/"must-not-exist.sqlite3"
    with pytest.raises(ValueError,match="SHA-256 mismatch"):
        restore_snapshot(Path(meta["manifest_file"]),dest)
    assert not dest.exists()


def test_manifest_file_path_traversal_is_rejected(tmp_path):
    _,meta=_backup(tmp_path)
    manifest=Path(meta["manifest_file"])
    obj=json.loads(manifest.read_text())
    obj["database_file"]="../outside.sqlite3"
    manifest.write_text(json.dumps(obj))
    with pytest.raises(ValueError,match="Unsafe"):
        read_manifest(manifest)


def test_non_crypt_rclone_remote_rejected(tmp_path,monkeypatch):
    _,meta=_backup(tmp_path)
    monkeypatch.setattr(subprocess,"run",lambda *args,**kwargs:
        subprocess.CompletedProcess(args[0],0,stdout="[plain]\ntype = drive\n",stderr=""))
    with pytest.raises(ValueError,match="not independently confirmed"):
        validate_crypt_remote("plain:")
    with pytest.raises(ValueError,match="Remote must"):
        prepare(Path(meta["manifest_file"]),"plain:/unsafe-subdir")


def _fake_crypt_runner(monkeypatch, *, tamper_roundtrip=False):
    storage={}
    def run(cmd,**kw):
        if cmd[:3]==["rclone","config","show"]:
            return subprocess.CompletedProcess(cmd,0,stdout="[meridyen_crypt]\ntype = crypt\n",stderr="")
        assert cmd[:2]==["rclone","copyto"]
        source,target=cmd[2:4]
        if source.startswith("meridyen_crypt:"):
            blob=storage[source]
            if tamper_roundtrip and source.endswith(".sqlite3"):
                blob=b"remote corrupted"
            Path(target).parent.mkdir(parents=True,exist_ok=True)
            Path(target).write_bytes(blob)
        else:
            if target.startswith("meridyen_crypt:"):
                assert "--immutable" in cmd
                if target in storage:
                    raise AssertionError("unexpected overwrite")
                storage[target]=Path(source).read_bytes()
            else:
                raise AssertionError("unexpected transfer")
        return subprocess.CompletedProcess(cmd,0,stdout="",stderr="")
    monkeypatch.setattr(subprocess,"run",run)
    return storage


def test_crypt_roundtrip_verified_and_restore_cloud(tmp_path,monkeypatch):
    _,meta=_backup(tmp_path)
    storage=_fake_crypt_runner(monkeypatch)
    manifest=Path(meta["manifest_file"])
    result=upload_verified(manifest,"meridyen_crypt:")
    assert result["status"]=="CLOUD_ROUNDTRIP_VERIFIED"
    assert result["remote_type"]=="crypt"
    assert storage
    dest=tmp_path/"cloud-recovered.sqlite3"
    recovered=download_verified(manifest,"meridyen_crypt:",dest)
    assert recovered["status"]=="RESTORED_NEW_DB_ONLY"
    assert dest.is_file()


def test_cloud_roundtrip_detects_corruption(tmp_path,monkeypatch):
    _,meta=_backup(tmp_path)
    _fake_crypt_runner(monkeypatch,tamper_roundtrip=True)
    with pytest.raises(ValueError,match="SHA-256 mismatch"):
        upload_verified(Path(meta["manifest_file"]),"meridyen_crypt:")


def test_cycle_requires_existing_database_and_rejects_overlapping_locks(tmp_path):
    db=tmp_path/"learning.sqlite3"
    backups=tmp_path/"backups"
    with pytest.raises(ValueError,match="missing"):
        cycle(db,backups)
    conn=connect(db)
    conn.close()
    lock=db.with_suffix(".sqlite3.cycle.lock")
    lock.write_text("already owned")
    with pytest.raises(ValueError,match="already owns"):
        cycle(db,backups)
    assert lock.exists()
    lock.unlink()
    result=cycle(db,backups)
    assert result["status"]=="COMPLETE_LOCAL_BACKUP"
    assert result["model_training_performed"] is False
    assert result["cloud_status"]=="DISABLED_LOCAL_ONLY"
    assert Path(result["local_report"]).exists()
    assert not lock.exists()


def test_cycle_cloud_requires_owner_authorization(tmp_path):
    db=tmp_path/"learning.sqlite3"
    con=connect(db)
    con.close()
    with pytest.raises(ValueError,match="crypt remote"):
        cycle(db,tmp_path/"backup",execute_cloud=True)


def test_disaster_restore_from_cloud_manifest_without_local_files(tmp_path,monkeypatch):
    db,meta=_backup(tmp_path)
    _fake_crypt_runner(monkeypatch)
    manifest=Path(meta["manifest_file"])
    uploaded=upload_verified(manifest,"meridyen_crypt:")
    assert uploaded["remote_manifest_verified"] is True
    # Simulate loss of BOTH the backup and its manifest.
    Path(meta["file"]).unlink()
    manifest_name=manifest.name
    manifest.unlink()
    dest=tmp_path/"disaster-restored.sqlite3"
    recovered=recover_from_cloud_manifest("meridyen_crypt:",manifest_name,dest)
    assert recovered["status"]=="RESTORED_NEW_DB_ONLY"
    assert dest.exists()
    conn=sqlite3.connect(dest)
    assert conn.execute("SELECT COUNT(*) FROM learning_v2_feedback").fetchone()[0]==1
    conn.close()


def test_cloud_disaster_restore_rejects_path_traversal(tmp_path,monkeypatch):
    _fake_crypt_runner(monkeypatch)
    with pytest.raises(ValueError,match="Unsafe cloud manifest"):
        recover_from_cloud_manifest("meridyen_crypt:","../malicious.manifest.json",
                                    tmp_path/"restored.sqlite3")
