from __future__ import annotations

"""Export stored WF5 S15.3 V1.4.1 scores to Meridyen plugin CSV without rescore.

No invented scores, raw price data, adjusted bars or PIT certification.
The output may be used only for separately audited research backtests.
"""
import argparse
import csv
import hashlib
import json
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

FORMULA = "S15.3_V1.4.1_CANONICAL_COMPLETION_2026-10-07"
# These are successful S15.3 V1.4 classifications, not exchange trade signals.
NON_NULL_STATUSES = {
    "PRECISION_CONFIRMED_12M_10X", "HIGH_SCORE_NOT_CONFIRMED",
    "STRONG_10X_WATCH", "10X_DISCOVERY", "NO_CANONICAL_GATE_STATUS",
    "EARLY_ASYMMETRIC", "EARLY_ASYMMETRIC_WATCH",
}
FIELDS = ["ticker", "signal_date", "model_version", "canonical_status",
          "score", "source_as_of", "source_id", "security_id",
          "source_run_id", "source_status"]


def export(db_path: Path, run_id: str, out_dir: Path) -> dict:
    if not db_path.is_file():
        raise ValueError("M10 SQLite database not found; no signals exported")
    db = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    try:
        run = db.execute(
            "SELECT status, start_date, end_date FROM wf5_replay_runs WHERE run_id=?",
            (run_id,),
        ).fetchone()
        if run is None or run["status"] != "COMPLETE":
            raise ValueError("WF5 run missing or not COMPLETE; refusing incomplete evidence")
        rows = db.execute("""
            SELECT observation_id, security_id, ticker, as_of_date, v141_score,
                   v141_status, outcome_status
            FROM wf5_replay_observations
            WHERE run_id=?
            ORDER BY as_of_date, security_id
        """, (run_id,)).fetchall()
    finally:
        db.close()
    if not rows:
        raise ValueError("WF5 run contains no observations")
    emitted = []
    excluded = {}
    seen = set()
    for row in rows:
        status = str(row["v141_status"] or "")
        score = row["v141_score"]
        if score is None or status.startswith("INCONCLUSIVE") or status.startswith("BLOCKED"):
            excluded["MISSING_CANONICAL_SCORE"] = excluded.get("MISSING_CANONICAL_SCORE", 0) + 1
            continue
        if not isinstance(score, (int, float)) or not 0 <= float(score) <= 100:
            raise ValueError("Nonfinite/out-of-range V1.4.1 score")
        # Classification labels may gain new versioned labels; never silently
        # treat an unexpected label as READY.
        if status not in NON_NULL_STATUSES:
            excluded["UNRECOGNIZED_STATUS"] = excluded.get("UNRECOGNIZED_STATUS", 0) + 1
            continue
        day = date.fromisoformat(str(row["as_of_date"]))
        key = (row["security_id"], day.isoformat())
        if key in seen:
            raise ValueError(f"Duplicate observation for security/date: {key}")
        seen.add(key)
        emitted.append({
            "ticker": row["ticker"], "signal_date": day.isoformat(),
            "model_version": FORMULA, "canonical_status": "READY",
            "score": float(score), "source_as_of": day.isoformat(),
            "source_id": row["observation_id"], "security_id": row["security_id"],
            "source_run_id": run_id, "source_status": status,
        })
    if not emitted:
        raise ValueError("No valid canonical scoring observations available")
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "meridyen_signals.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(emitted)
    report = {
        "schema": "MERIDYEN_PHASE13_EXPORT_V1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "wf5_run_id": run_id,
        "wf5_run_status": run["status"],
        "model_version": FORMULA,
        "n_source_observations": len(rows),
        "n_exported": len(emitted),
        "excluded": excluded,
        "csv_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
        "pit_verified": False,
        "data_completeness_verified": False,
        "status": "EXPORT_READY_FOR_INPUT_AUDIT",
        "required_next": [
            "Run WF9 complete-universe PIT data readiness and activation audit",
            "Supply canonical adjusted daily OHLC with delisted coverage",
            "Run Meridyen v0.12 daily event / portfolio backtest explicitly",
        ],
        "warning": "source_as_of is WF5 analysis session, NOT a verified issuer filing available_at timestamp; WF5 is responsible for upstream feature-time integrity. Never infer a trade recommendation from exported score.",
    }
    (out_dir / "phase13_export_manifest.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True, type=Path)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--out-dir", required=True, type=Path)
    args = ap.parse_args()
    try:
        result = export(args.db, args.run_id, args.out_dir)
    except (ValueError, sqlite3.Error, OSError) as e:
        ap.exit(2, "PHASE13_EXPORT_BLOCKED: " + str(e) + "\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
