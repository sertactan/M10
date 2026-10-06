from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


class SQLiteStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self.last_recovery_backup: Path | None = None

    @property
    def connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
        return self._conn

    @staticmethod
    def _validate_schema_asset(schema_path: Path) -> str:
        if not schema_path.exists():
            raise RuntimeError(f"Packaged SQLite schema is missing: {schema_path}")
        sql = schema_path.read_text(encoding="utf-8")
        required_markers = (
            "CREATE TABLE IF NOT EXISTS security_master",
            "CREATE TABLE IF NOT EXISTS canonical_price_selection",
            "CREATE TABLE IF NOT EXISTS provider_health_state",
            "CREATE TABLE IF NOT EXISTS background_sync_tasks",
        )
        missing = [marker for marker in required_markers if marker not in sql]
        if missing:
            raise RuntimeError(
                "Packaged SQLite schema is incomplete: " + ", ".join(missing)
            )
        return sql

    def _integrity_ok(self) -> bool:
        row = self.connection.execute("PRAGMA quick_check").fetchone()
        return row is not None and str(row[0]).lower() == "ok"

    def _recover_corrupt_database(self) -> Path:
        self.close()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = self.db_path.with_name(
            f"{self.db_path.name}.corrupt-{stamp}.bak"
        )
        if self.db_path.exists():
            os.replace(self.db_path, backup)

        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(self.db_path) + suffix)
            if sidecar.exists():
                sidecar_backup = backup.with_name(backup.name + suffix)
                os.replace(sidecar, sidecar_backup)

        self.last_recovery_backup = backup
        return backup

    def initialize(
        self,
        schema_path: str | Path | None = None,
        *,
        recover_corrupt: bool = True,
    ) -> None:
        if schema_path is None:
            schema_path = Path(__file__).with_name("schema.sql")
        schema = Path(schema_path)
        sql = self._validate_schema_asset(schema)

        # Check integrity before running migrations. Only true corruption is
        # eligible for automatic recovery; migration/locking errors propagate.
        try:
            integrity_ok = self._integrity_ok()
        except sqlite3.DatabaseError:
            integrity_ok = False

        if not integrity_ok:
            if not recover_corrupt:
                raise sqlite3.DatabaseError(
                    f"SQLite integrity check failed: {self.db_path}"
                )
            self._recover_corrupt_database()
            # Re-open an empty database and fail closed if that fresh DB cannot
            # initialize correctly.
            self.initialize(schema, recover_corrupt=False)
            return

        # Older databases may predate columns referenced by indexes in the
        # current schema. Add compatibility columns before executescript so a
        # normal in-place upgrade does not fail before migrations can run.
        self._apply_compatibility_migrations()
        self.connection.executescript(sql)
        self._apply_compatibility_migrations()
        self.connection.commit()

        if not self._integrity_ok():
            raise sqlite3.DatabaseError(
                f"SQLite integrity check failed after initialization: {self.db_path}"
            )

    def _table_exists(self, table: str) -> bool:
        row = self.connection.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type='table' AND name=?
            LIMIT 1
            """,
            (table,),
        ).fetchone()
        return row is not None

    def _column_names(self, table: str) -> set[str]:
        if not self._table_exists(table):
            return set()
        return {
            str(row["name"])
            for row in self.connection.execute(f"PRAGMA table_info({table})")
        }

    def _ensure_column(self, table: str, column: str, definition: str) -> None:
        if not self._table_exists(table):
            return
        if column not in self._column_names(table):
            self.connection.execute(
                f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
            )

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
