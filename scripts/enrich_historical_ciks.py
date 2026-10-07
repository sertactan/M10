from __future__ import annotations

import asyncio
from pathlib import Path

from app.bootstrap import AppContainer
from core.universe.identity import normalize_name
from data.providers.sec_cik_lookup import SecCikNameLookupProvider


async def run() -> int:
    root = Path(__file__).resolve().parents[1]
    app = AppContainer(root)
    app.initialize()
    try:
        cache = app.resolve_data_path("sec_mirror/cik-lookup-data.txt")
        mapping = await SecCikNameLookupProvider().load(cache)
        rows = app.sqlite.connection.execute(
            """
            SELECT security_id,name
            FROM security_master
            WHERE market='US' AND (cik IS NULL OR cik='')
            """
        ).fetchall()
        matched = 0
        for row in rows:
            cik = mapping.get(normalize_name(str(row["name"] or "")))
            if cik is None:
                continue
            app.sqlite.connection.execute(
                """
                UPDATE security_master
                SET cik=?, updated_at=datetime('now')
                WHERE security_id=? AND (cik IS NULL OR cik='')
                """,
                (cik, row["security_id"]),
            )
            matched += 1
        app.sqlite.connection.commit()
        print(f"SEC UNIQUE-NAME CIK MAPPINGS AVAILABLE: {len(mapping)}")
        print(f"HISTORICAL/UNRESOLVED SECURITIES ENRICHED: {matched}")
        print("MATCH POLICY: normalized exact unique company name only; ambiguous names skipped")
        return 0
    finally:
        app.close()


def main() -> int:
    return asyncio.run(run())


if __name__ == "__main__":
    raise SystemExit(main())
