"""Read-only inventory of SEC-origin S14 inputs in the existing local archives.

Never interprets an absent metric as zero, or an archive timestamp as proven PIT.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
import json
from pathlib import Path
import sqlite3


def _readonly(path: Path) -> sqlite3.Connection:
    if path.is_symlink() or not path.is_file():
        raise ValueError("The source database must be an existing regular file")
    db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    db.execute("PRAGMA query_only=ON")
    return db


def inventory(phase27: Path, archive: Path, ticker: str) -> dict:
    with closing(_readonly(phase27)) as db:
        security = db.execute(
            "SELECT security_id,checked_at FROM stock_runs WHERE ticker=?", (ticker,)
        ).fetchone()
        if not security:
            raise ValueError("Ticker not found in existing phase27 stage")
        sid, at = security
        facts = db.execute(
            "SELECT metric FROM research_facts WHERE ticker=?", (ticker,)
        ).fetchall()
    with closing(_readonly(archive)) as db:
        rows = db.execute(
            "SELECT metric_name,period_kind,period_end,COUNT(*) FROM fundamental_facts_source "
            "WHERE security_id=? AND source='SEC_EDGAR' "
            "GROUP BY metric_name,period_kind,period_end", (sid,)
        ).fetchall()
    by_metric: dict[str, set[str]] = {}
    for metric, kind, end, count in rows:
        by_metric.setdefault(metric, set()).add(f"{kind}:{end}")
    return {
        "ticker": ticker, "as_of": at,
        "scope": "READ_ONLY_LOCAL_ARCHIVE_INVENTORY_NOT_PIT",
        "phase27_metrics": dict(sorted(Counter(r[0] for r in facts).items())),
        "archive_metric_periods": {k: {"period_count": len(v), "latest_three": sorted(v)[-3:]}
                                   for k, v in sorted(by_metric.items())},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase27", required=True, type=Path)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--ticker", default="INOD")
    args = parser.parse_args()
    print(json.dumps(inventory(args.phase27, args.archive, args.ticker), indent=2))


if __name__ == "__main__":
    main()
