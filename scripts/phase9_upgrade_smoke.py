from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


LEGACY_SCHEMA = """
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


def create_legacy(db_path: Path) -> int:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(LEGACY_SCHEMA)
        connection.commit()
    finally:
        connection.close()
    print(f"Created legacy database: {db_path}")
    return 0


def verify_upgrade(db_path: Path) -> int:
    connection = sqlite3.connect(db_path)
    try:
        security_columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(security_master)")
        }
        alias_columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(ticker_aliases)")
        }
        legacy = connection.execute(
            "SELECT ticker FROM security_master WHERE security_id='LEGACY-1'"
        ).fetchone()
        us_rows = connection.execute(
            "SELECT COUNT(*) FROM security_master WHERE market='US'"
        ).fetchone()[0]
        quick_check = connection.execute("PRAGMA quick_check").fetchone()[0]
    finally:
        connection.close()

    required_security = {
        "country_code",
        "listing_key",
        "source_scope",
        "source_priority",
        "first_seen",
        "last_seen",
    }
    required_aliases = {
        "source",
        "event_type",
        "availability_date",
        "ingested_at",
    }

    missing_security = sorted(required_security - security_columns)
    missing_aliases = sorted(required_aliases - alias_columns)
    if missing_security:
        raise RuntimeError(
            "Upgrade missing security_master columns: "
            + ", ".join(missing_security)
        )
    if missing_aliases:
        raise RuntimeError(
            "Upgrade missing ticker_aliases columns: "
            + ", ".join(missing_aliases)
        )
    if legacy is None or legacy[0] != "OLD":
        raise RuntimeError("Legacy security row was not preserved")
    if int(us_rows) < 1000:
        raise RuntimeError(f"Offline US bootstrap incomplete after upgrade: {us_rows}")
    if quick_check != "ok":
        raise RuntimeError(f"SQLite quick_check failed after upgrade: {quick_check}")

    print(
        f"Upgrade verified: US rows={us_rows}, "
        f"legacy={legacy[0]}, quick_check={quick_check}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("create", "verify"))
    parser.add_argument("db_path")
    args = parser.parse_args()

    path = Path(args.db_path)
    if args.mode == "create":
        return create_legacy(path)
    return verify_upgrade(path)


if __name__ == "__main__":
    raise SystemExit(main())
