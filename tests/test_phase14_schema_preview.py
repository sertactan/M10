from __future__ import annotations

import hashlib
from pathlib import Path
import sqlite3

import pytest

from data.database.sqlite_store import SQLiteStore
from scripts.phase14_schema_preview import preview, REQUIRED


def _source(tmp_path: Path) -> Path:
    original=tmp_path/"live"/"operational.db"
    store=SQLiteStore(original)
    store.initialize()
    store.connection.execute(
        """INSERT INTO security_master
           (security_id,ticker,name,exchange,market,active,created_at,updated_at)
           VALUES ('SEC-A','TEST','Example Inc','NASDAQ','US',1,?,?)""",
        ("2026-10-08T00:00:00Z", "2026-10-08T00:00:00Z"),
    )
    store.connection.execute(
        """INSERT INTO universe_snapshot_membership
           (snapshot_date,security_id,ticker,exchange,exchange_mic,
            source,availability_date,ingested_at)
           VALUES ('2026-06-01','SEC-A','TEST','NASDAQ','XNAS',
                   'SNAPSHOT_2026',?,?)""",
        ("2026-06-01","2026-06-01"),
    )
    store.connection.commit()
    store.close()
    # Simulate legacy installed app without the WF5/WF6 tables.
    with sqlite3.connect(original) as con:
        for tab in REQUIRED:
            if tab.startswith(("wf5_", "wf6_")):
                con.execute("DROP TABLE IF EXISTS "+tab)
    return original


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_real_schema_preview_on_copy_adds_wf5_wf6_preserves_all_existing_rows(tmp_path):
    source=_source(tmp_path)
    before=_digest(source)
    backups=tmp_path/"external_backups"
    result=preview(source,backups)
    assert result["status"]=="SCHEMA_PREVIEW_SAFE_ON_COPY_ONLY", result["reason"]
    assert result["pre_existing_rows_preserved"] is True
    assert result["snapshot_integrity"]=="ok"
    assert result["preview_integrity"]=="ok"
    assert result["missing_required_tables"]==[]
    assert "wf5_replay_runs" in result["added_schema_tables"]
    assert "wf6_walk_forward_runs" in result["added_schema_tables"]
    assert _digest(source)==before
    with sqlite3.connect(source) as live:
        assert live.execute("SELECT COUNT(*) FROM security_master").fetchone()[0]==1
        assert live.execute("SELECT COUNT(*) FROM universe_snapshot_membership").fetchone()[0]==1
        assert live.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='wf5_replay_runs'"
        ).fetchone() is None
    with sqlite3.connect(result["preview_file"]) as staged:
        assert staged.execute("SELECT COUNT(*) FROM security_master").fetchone()[0]==1
        assert staged.execute("SELECT COUNT(*) FROM universe_snapshot_membership").fetchone()[0]==1
        assert staged.execute("PRAGMA integrity_check").fetchone()[0]=="ok"


def test_preview_never_replaces_backups(tmp_path):
    source=_source(tmp_path)
    backups=tmp_path/"backups"
    first=preview(source,backups)
    second=preview(source,backups)
    assert first["snapshot_file"]!=second["snapshot_file"]
    assert Path(first["snapshot_file"]).exists()
    assert Path(second["snapshot_file"]).exists()
    assert first["snapshot_sha256"]==second["snapshot_sha256"]


def test_corrupt_source_fails_without_mutation_and_preserves_error_report(tmp_path):
    source=tmp_path/"operational.db"
    source.write_bytes(b"not valid sqlite")
    old=_digest(source)
    result=preview(source,tmp_path/"backups")
    assert result["status"]=="SCHEMA_PREVIEW_BLOCKED"
    assert "integrity" in result["reason"] or "DatabaseError" in result["reason"]
    assert _digest(source)==old
    assert Path(result["report_file"]).is_file()


def test_missing_source_refuses_preparation(tmp_path):
    backups=tmp_path/"backups"
    with pytest.raises(ValueError,match="not found"):
        preview(tmp_path/"missing.db",backups)
    assert not backups.exists()


def test_refuse_private_backup_inside_public_git_repo(tmp_path):
    source=_source(tmp_path)
    fake_repo=tmp_path/"public_repo"
    fake_repo.mkdir()
    with pytest.raises(ValueError,match="outside"):
        preview(source,fake_repo/"data/runtime/backups",repo_root=fake_repo)
    assert not (fake_repo/"data/runtime/backups").exists()
