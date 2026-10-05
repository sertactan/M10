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
        self.connection.commit()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "SQLiteStore":
        self.initialize()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
