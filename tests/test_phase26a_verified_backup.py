"""Critical backup and restore behavior on disposable SQLite fixtures."""
from pathlib import Path
import sqlite3

import pytest

from scripts.phase26a_verified_backup import inventory


def test_verified_snapshot_restores_sqlite_and_private_file(tmp_path: Path) -> None:
    db = tmp_path / "live" / "operational.db"
    db.parent.mkdir()
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE facts (id INTEGER PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO facts(value) VALUES ('evidence')")
    source = tmp_path / "private.csv"
    source.write_text("ticker\nBKE\n", encoding="utf-8")
    out = tmp_path / "backup"
    report = inventory(db, {"source/private.csv": source}, out)
    assert report["status"] == "BACKUP_AND_RESTORE_VERIFIED"
    assert all(row["restored_sha256_matches"] for row in report["entries"])
    assert all(row["restored_quick_check"] == "ok" for row in report["entries"]
               if row["method"] == "SQLITE_ONLINE_BACKUP")
    with sqlite3.connect(out / "restore_probe" / "operational.db") as conn:
        assert conn.execute("SELECT value FROM facts").fetchone()[0] == "evidence"
    assert source.read_text(encoding="utf-8") == "ticker\nBKE\n"
    with pytest.raises(ValueError, match="must be new"):
        inventory(db, {"source/private.csv": source}, out)
