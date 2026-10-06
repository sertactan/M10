from __future__ import annotations

import sqlite3
from pathlib import Path


class SQLiteStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    @property
    def connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
        return self._conn

    def initialize(self, schema_path: str | Path | None = None) -> None:
        if schema_path is None:
            schema_path = Path(__file__).with_name("schema.sql")
        sql = Path(schema_path).read_text(encoding="utf-8")
        self.connection.executescript(sql)
        self._apply_compatibility_migrations()
        self.connection.commit()

    def _column_names(self, table: str) -> set[str]:
        return {row["name"] for row in self.connection.execute(f"PRAGMA table_info({table})")}

    def _ensure_column(self, table: str, column: str, definition: str) -> None:
        if column not in self._column_names(table):
            self.connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def _apply_compatibility_migrations(self) -> None:
        for column, definition in {
            "primary_exchange_mic": "TEXT",
            "security_type": "TEXT",
            "currency": "TEXT",
            "locale": "TEXT",
            "composite_figi": "TEXT",
            "share_class_figi": "TEXT",
            "listing_key": "TEXT",
            "country": "TEXT",
            "country_code": "TEXT",
            "isin": "TEXT",
            "asset_type": "TEXT",
            "aliases": "TEXT",
            "source_scope": "TEXT NOT NULL DEFAULT 'CANONICAL'",
            "redistribution_status": "TEXT",
            "source_priority": "INTEGER NOT NULL DEFAULT 99",
            "first_seen": "TEXT",
            "last_seen": "TEXT",
        }.items():
            self._ensure_column("security_master", column, definition)

        for column, definition in {
            "source": "TEXT NOT NULL DEFAULT 'UNKNOWN'",
            "event_type": "TEXT NOT NULL DEFAULT 'alias'",
            "availability_date": "TEXT",
            "ingested_at": "TEXT",
        }.items():
            self._ensure_column("ticker_aliases", column, definition)

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "SQLiteStore":
        self.initialize()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
