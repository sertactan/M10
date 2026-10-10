"""Phase25V: read-only inventory of *local* M10 mature learning records.

The presence of labels never proves independently audited PIT, 10X performance,
complete universe coverage or model training. No write, import or promotion path.
Run using --operational-db and --learning-db pointing at the same Windows runtime.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
import sqlite3

SCHEMA = "MERIDYEN_PHASE25V_LOCAL_MATURE_LEARNING_INVENTORY_V1"
MARKET_TABLES = ("wf5_replay_runs", "wf6_walk_forward_runs", "wf5_replay_observations")
LEARNING_TABLES = (
    "learning_v2_wf5_batches", "learning_v2_wf5_mature_labels",
    "learning_v2_outcomes", "learning_v2_research_observations",
)


def _read_db(path: Path):
    if not path.is_file() or path.is_symlink():
        raise ValueError("LOCAL_SQLITE_NOT_ACCESSIBLE")
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    return connection


def _tables(conn):
    return {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}


def _count(conn, available, name):
    # Only constant table identifiers from this module are supplied.
    return int(conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]) if name in available else None


def _complete(conn, available, name):
    return int(conn.execute(
        f"SELECT COUNT(*) FROM {name} WHERE status='COMPLETE'").fetchone()[0]) if name in available else None


def _maturity_summary(conn, available, cutoff):
    if not {"learning_v2_wf5_batches", "learning_v2_wf5_mature_labels"} <= available:
        return {"status": "NO_NATIVE_WF5_LABEL_TABLES", "rows": None,
                "distinct_security_signal_dates": None, "mature_by_cutoff": None,
                "hit_2x": None, "hit_5x": None, "hit_10x": None}
    batches = {r["digest"]: r for r in conn.execute(
        "SELECT digest, run_id, cutoff, source_pit_verified, mature_count "
        "FROM learning_v2_wf5_batches")}
    counts = {"rows": 0, "mature_by_cutoff": 0, "hit_2x": 0, "hit_5x": 0,
              "hit_10x": 0, "bad_availability": 0, "bad_horizon": 0,
              "unmatched_batch": 0,
              "batch_claims_pit": sum(int(bool(r["source_pit_verified"])) for r in batches.values())}
    unique = set()
    valid = set()
    # No private ticker or individual signal is placed in the result.
    for r in conn.execute("SELECT digest, security_id, signal_date, label_available_at, "
                          "horizon_sessions, hit_2x, hit_5x, hit_10x "
                          "FROM learning_v2_wf5_mature_labels"):
        counts["rows"] += 1
        key = (r["security_id"], r["signal_date"])
        unique.add(key)
        if r["digest"] not in batches:
            counts["unmatched_batch"] += 1
            continue
        if r["horizon_sessions"] != 252:
            counts["bad_horizon"] += 1
            continue
        try:
            signal = date.fromisoformat(str(r["signal_date"]))
            avail = datetime.fromisoformat(str(r["label_available_at"]))
            if avail.tzinfo is None or avail.utcoffset() is None:
                raise ValueError("timezone missing")
            available_day = avail.astimezone(timezone.utc).date()
            if available_day <= signal:
                raise ValueError("label precedes signal maturity")
        except (ValueError, TypeError):
            counts["bad_availability"] += 1
            continue
        if available_day > cutoff:
            continue
        # Across batches a security/date may repeat. Do not double count hits.
        if key not in valid:
            valid.add(key)
            counts["mature_by_cutoff"] += 1
            for hit in ("hit_2x", "hit_5x", "hit_10x"):
                if r[hit] == 1:
                    counts[hit] += 1
        # Conflicting duplicate batch contents require a separate hash audit.
    counts["distinct_security_signal_dates"] = len(unique)
    counts["duplicate_across_batches"] = counts["rows"] - len(unique)
    counts["batches"] = len(batches)
    counts["batch_mature_count_sum"] = sum(int(r["mature_count"]) for r in batches.values())
    counts["status"] = ("DB_REPORTED_MATURE_NOT_PIT_CERTIFIED" if counts["mature_by_cutoff"]
                        else "NO_DB_REPORTED_MATURE_BY_CUTOFF")
    return counts


def inspect(operational_db, learning_db, cutoff):
    day = date.fromisoformat(str(cutoff))
    if day > datetime.now(timezone.utc).date():
        raise ValueError("FUTURE_CUTOFF")
    if Path(operational_db).resolve() == Path(learning_db).resolve():
        raise ValueError("SOURCE_DATABASES_MUST_BE_DISTINCT")
    try:
        market = _read_db(Path(operational_db))
    except (ValueError, sqlite3.Error):
        market = None
    try:
        learning = _read_db(Path(learning_db))
    except (ValueError, sqlite3.Error):
        learning = None
    try:
        m = _tables(market) if market is not None else set()
        l = _tables(learning) if learning is not None else set()
        sources = {
            "market_database_opened_readonly": market is not None,
            "learning_database_opened_readonly": learning is not None,
            "wf5_complete_runs": _complete(market, m, "wf5_replay_runs") if market else None,
            "wf6_complete_runs": _complete(market, m, "wf6_walk_forward_runs") if market else None,
            "wf5_observations": _count(market, m, "wf5_replay_observations") if market else None,
            "legacy_completed_outcomes_not_pit_certified": (
                int(learning.execute("SELECT COUNT(*) FROM learning_v2_outcomes WHERE completed=1").fetchone()[0])
                if learning is not None and "learning_v2_outcomes" in l else None),
            "research_only_routes": (_count(learning, l, "learning_v2_research_observations")
                                     if learning is not None else None),
        }
        label = (_maturity_summary(learning, l, day) if learning is not None else
                 {"status": "LEARNING_DB_UNAVAILABLE", "rows": None,
                  "mature_by_cutoff": None, "hit_10x": None})
        return {"schema": SCHEMA, "as_of_utc_date": day.isoformat(),
                "status": ("INVENTORY_ONLY_NOT_PIT_CERTIFIED" if market and learning else
                           "LOCAL_DATABASE_ACCESS_BLOCKED"),
                "source_counts": sources, "native_wf5_labels": label,
                "independently_certified_mature_labels": None,
                "pit_certification": "NOT_ESTABLISHED_BY_THIS_INVENTORY",
                "learning_v3_trained": "NOT_ESTABLISHED_BY_THIS_INVENTORY",
                "model_scoring_or_db_mutation": False}
    finally:
        if market is not None:
            market.close()
        if learning is not None:
            learning.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--operational-db", required=True, type=Path)
    p.add_argument("--learning-db", required=True, type=Path)
    p.add_argument("--cutoff", default=datetime.now(timezone.utc).date().isoformat())
    args = p.parse_args()
    try:
        print(json.dumps(inspect(args.operational_db, args.learning_db, args.cutoff),
                         indent=2, ensure_ascii=False))
    except (ValueError, OSError, sqlite3.Error) as exc:
        p.exit(2, "PHASE25V_INVENTORY_BLOCKED: " + str(exc) + "\n")


if __name__ == "__main__":
    main()
