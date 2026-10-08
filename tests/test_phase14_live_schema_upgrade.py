from __future__ import annotations

import hashlib
import os
from pathlib import Path
import sqlite3

import pytest

from data.database.sqlite_store import SQLiteStore
from scripts.phase14_live_schema_upgrade import migrate
from scripts.phase14_schema_preview import REQUIRED


def _old_database(tmp_path):
    src = tmp_path / "application" / "operational.db"
    m = SQLiteStore(src)
    m.initialize()
    m.connection.execute(
        """INSERT INTO security_master
           (security_id,ticker,name,exchange,market,active,created_at,updated_at)
           VALUES ('SEC-EXAMPLE','EXAMPLE','Example','NASDAQ','US',1,?,?)""",
        ("2026-10-08T00:00:00Z", "2026-10-08T00:00:00Z"),
    )
    m.connection.commit()
    m.close()
    with sqlite3.connect(src) as conn:
        for table in REQUIRED:
            if table.startswith(("wf5_", "wf6_")):
                conn.execute("DROP TABLE IF EXISTS " + table)
    return src


def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def test_dry_run_never_changes_live_source(tmp_path):
    source = _old_database(tmp_path)
    original_sha = _digest(source)
    result = migrate(source,tmp_path/"backups",repo_root=tmp_path/"other")
    assert result["status"]=="APPLY_READY_REQUIRES_EXPLICIT_OWNER_CONFIRMATION"
    assert result["live_database_modified"] is False
    assert result["rollback_file"] is None
    assert result["existing_table_counts_preserved"] is True
    assert _digest(source)==original_sha
    assert Path(result["backup_snapshot"]).is_file()
    with sqlite3.connect(source) as conn:
        names={x[0] for x in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "wf6_walk_forward_runs" not in names


def test_explicit_apply_preserves_records_and_retains_original_for_rollback(tmp_path):
    source=_old_database(tmp_path)
    original_sha=_digest(source)
    result=migrate(
        source,tmp_path/"backups",repo_root=tmp_path/"other",apply=True,
        confirm_app_closed=True,confirm_source_exact=str(source))
    assert result["status"]=="LIVE_SCHEMA_UPGRADED_WITH_ROLLBACK_RETAINED"
    assert result["live_database_modified"] is True
    assert Path(result["rollback_file"]).is_file()
    assert _digest(result["rollback_file"])==original_sha
    assert Path(result["backup_snapshot"]).exists()
    with sqlite3.connect(source) as conn:
        assert conn.execute("SELECT COUNT(*) FROM security_master").fetchone()[0]==1
        assert conn.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
        names={x[0] for x in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert set(REQUIRED).issubset(names)
    assert result["historical_pit_data_added"] is False
    assert result["wf9_activated"] is False


def test_without_explicit_confirmation_apply_refused_before_preview(tmp_path):
    src=_old_database(tmp_path)
    before=_digest(src)
    for kwargs in [
        {"apply":True},
        {"apply":True,"confirm_app_closed":True},
        {"apply":True,"confirm_app_closed":True,"confirm_source_exact":str(tmp_path/"wrong.db")},
    ]:
        with pytest.raises(ValueError,match="requires"):
            migrate(src,tmp_path/"backups",repo_root=tmp_path/"other",**kwargs)
    assert _digest(src)==before
    assert not (tmp_path/"backups").exists()


@pytest.mark.parametrize("suffix",["-wal","-shm","-journal"])
def test_any_sidecar_prevents_mutating_live_database(tmp_path,suffix):
    src=_old_database(tmp_path)
    Path(str(src)+suffix).write_bytes(b"unknown pending SQLite state")
    before=_digest(src)
    with pytest.raises(ValueError,match="journal/sidecar"):
        migrate(src,tmp_path/"backups",repo_root=tmp_path/"other",apply=True,
                confirm_app_closed=True,confirm_source_exact=str(src))
    assert _digest(src)==before
    assert Path(str(src)+suffix).exists()


def test_install_failure_restores_original_bytes_and_keeps_backup(tmp_path,monkeypatch):
    src=_old_database(tmp_path)
    before=_digest(src)
    actual_rename=os.rename
    def interrupted_rename(source,target):
        if ".phase14-stage-" in str(source) and Path(target)==src:
            raise PermissionError("simulated new DB install failure")
        return actual_rename(source,target)
    monkeypatch.setattr(os,"rename",interrupted_rename)
    with pytest.raises(PermissionError,match="simulated"):
        migrate(src,tmp_path/"backups",repo_root=tmp_path/"other",apply=True,
                confirm_app_closed=True,confirm_source_exact=str(src))
    assert src.exists()
    assert _digest(src)==before
    assert list((tmp_path/"backups").glob("operational_pre_schema_*.sqlite3"))


def test_missing_live_database_rejected(tmp_path):
    with pytest.raises(ValueError,match="does not exist"):
        migrate(tmp_path/"missing.db",tmp_path/"backups")
    assert not (tmp_path/"backups").exists()
