from __future__ import annotations

import argparse
from pathlib import Path

from core.historical.s16_runtime import resolve_security_id
from data.database.sqlite_store import SQLiteStore
from data.providers.s16_archive_csv import read_feature_evidence_csv
from data.repositories.s16_evidence_repository import S16EvidenceRepository


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import direct point-in-time S16 feature evidence."
    )
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--input", required=True, type=Path)
    args = parser.parse_args()

    store = SQLiteStore(args.db)
    store.initialize()
    repo = S16EvidenceRepository(store)

    def resolver(ticker, as_of_date):
        return resolve_security_id(
            store.connection, ticker=ticker, as_of_date=as_of_date
        )

    rows = read_feature_evidence_csv(args.input, resolve_security_id=resolver)
    for row in rows:
        repo.save_feature_evidence(row)
    print(f"imported {len(rows)} direct S16 evidence rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
