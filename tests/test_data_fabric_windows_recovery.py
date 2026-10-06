from __future__ import annotations

import sqlite3
from pathlib import Path

from core.runtime.paths import verify_writable_runtime
from data.database.sqlite_store import SQLiteStore


SCHEMA = Path(__file__).resolve().parents[1] / "data" / "database" / "schema.sql"


def test_writable_runtime_probe_leaves_no_artifact(tmp_path):
    root = tmp_path / "runtime"
    assert verify_writable_runtime(root) == root
    assert root.is_dir()
    assert list(root.glob(".s153-write-probe-*.tmp")) == []


def test_corrupt_sqlite_is_preserved_and_rebuilt(tmp_path):
    db = tmp_path / "operational.db"
    db.write_bytes(b"this is not a sqlite database")

    store = SQLiteStore(db)
    try:
        store.initialize(SCHEMA)
        assert store.last_recovery_backup is not None
        assert store.last_recovery_backup.exists()
        assert store.last_recovery_backup.read_bytes() == b"this is not a sqlite database"
        assert store.connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        assert store.connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='security_master'"
        ).fetchone() is not None
    finally:
        store.close()


def test_legacy_database_migrates_before_new_indexes_are_created(tmp_path):
    db = tmp_path / "legacy.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE security_master (
            security_id TEXT PRIMARY KEY,
            ticker TEXT NOT NULL,
            name TEXT NOT NULL,
            exchange TEXT NOT NULL,
            market TEXT NOT NULL DEFAULT 'US',
            cik TEXT,
            sector TEXT,
            industry TEXT,
            ipo_date TEXT,
            delisted_date TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE ticker_aliases (
            alias TEXT NOT NULL,
            security_id TEXT NOT NULL,
            valid_from TEXT NOT NULL DEFAULT '',
            valid_to TEXT,
            PRIMARY KEY(alias, security_id, valid_from)
        );

        INSERT INTO security_master (
            security_id,ticker,name,exchange,market,active,created_at,updated_at
        ) VALUES (
            'LEGACY-1','OLD','Legacy Corp','NASDAQ','US',1,
            '2025-01-01T00:00:00+00:00','2025-01-01T00:00:00+00:00'
        );
        """
    )
    conn.commit()
    conn.close()

    store = SQLiteStore(db)
    try:
        store.initialize(SCHEMA)
        security_columns = store._column_names("security_master")
        alias_columns = store._column_names("ticker_aliases")

        assert {
            "country_code",
            "listing_key",
            "source_scope",
            "source_priority",
            "first_seen",
            "last_seen",
        }.issubset(security_columns)
        assert {
            "source",
            "event_type",
            "availability_date",
            "ingested_at",
        }.issubset(alias_columns)

        assert store.connection.execute(
            "SELECT ticker FROM security_master WHERE security_id='LEGACY-1'"
        ).fetchone()["ticker"] == "OLD"
        assert store.connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='index' AND name='idx_security_country_code'"
        ).fetchone() is not None
        assert store.last_recovery_backup is None
    finally:
        store.close()


def test_missing_or_incomplete_packaged_schema_fails_closed(tmp_path):
    db = tmp_path / "db.sqlite"
    bad_schema = tmp_path / "schema.sql"
    bad_schema.write_text(
        "CREATE TABLE IF NOT EXISTS security_master (security_id TEXT PRIMARY KEY);",
        encoding="utf-8",
    )

    store = SQLiteStore(db)
    try:
        try:
            store.initialize(bad_schema)
        except RuntimeError as exc:
            assert "schema is incomplete" in str(exc)
        else:
            raise AssertionError("incomplete schema should fail closed")
    finally:
        store.close()
