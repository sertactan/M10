"""Reproducible, read-only *experimental* Phase25W fixed-cohort price diagnostic.

The cohort was chosen ex post and the source adjusted prices are not certified.
This is never canonical performance, WF9, a model score or an investable result.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
from contextlib import closing

SCHEMA = "phase25y_experimental_research_backtest_v1"
START_MONTH, END_MONTH = "2024-01", "2025-09"
LIMITATIONS = (
    "LOOKAHEAD: 25 names were selected using full-window 438-bar coverage and retrospective 2026 membership files.",
    "SURVIVORSHIP: ex-post fixed cohort excludes missing, delisted and conflicting historical issuers; bias cannot be quantified from this subset.",
    "AVAILABLE_AT: SEC feature publication/ingestion was not audited; no SEC features enter this price-only arithmetic.",
    "ADJUSTMENT: SimFin source Adj. Close is hindsight-adjusted and has no independent factor or distribution-rights certificate.",
    "DELISTING: terminal payoffs and complete corporate actions are unavailable; missing names would not be silently filled.",
    "NO_TRADING: month-end rebalance arithmetic ignores execution, spreads, costs, taxes, borrow and capacity.",
)


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        h = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"missing or linked input: {path}")
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def months() -> list[str]:
    return [f"{y:04d}-{m:02d}" for y in (2024, 2025) for m in range(1, 13)
            if START_MONTH <= f"{y:04d}-{m:02d}" <= END_MONTH]


def month_end_series(bars: list[tuple], expected_count: int) -> dict[str, dict]:
    if len(bars) != expected_count or len({r[0] for r in bars}) != len(bars):
        raise ValueError("price coverage or unique trade-date mismatch")
    by_month = {}
    for day, adj, close in sorted(bars):
        if not (isinstance(day, str) and len(day) == 10 and math.isfinite(adj)
                and math.isfinite(close) and adj > 0 and close > 0):
            raise ValueError("invalid source price row")
        month = day[:7]
        if START_MONTH <= month <= END_MONTH:
            by_month[month] = {"trade_date": day, "adj_close": adj, "close": close}
    if sorted(by_month) != months():
        raise ValueError("missing monthly source price endpoint")
    return by_month


def equal_weight_path(series: dict[str, dict[str, dict]]) -> dict:
    ordered_months = months()
    tickers = sorted(series)
    if not tickers:
        raise ValueError("empty cohort")
    nav_adj, nav_close = 1.0, 1.0
    intervals = []
    for prior, current in zip(ordered_months, ordered_months[1:]):
        per_name = []
        for ticker in tickers:
            before, after = series[ticker][prior], series[ticker][current]
            per_name.append((ticker, after["adj_close"] / before["adj_close"] - 1,
                             after["close"] / before["close"] - 1))
        mean_adj = sum(row[1] for row in per_name) / len(tickers)
        mean_close = sum(row[2] for row in per_name) / len(tickers)
        nav_adj *= 1 + mean_adj
        nav_close *= 1 + mean_close
        intervals.append({"from_month": prior, "to_month": current,
                          "mean_source_adj_return": round(mean_adj, 10),
                          "mean_source_close_return": round(mean_close, 10),
                          "source_adj_index": round(nav_adj, 10),
                          "source_close_index": round(nav_close, 10),
                          "largest_abs_source_adj_contributor": max(per_name, key=lambda row: abs(row[1]))[0],
                          "largest_abs_source_adj_single_name_return": round(max(per_name, key=lambda row: abs(row[1]))[1], 10)})
    return {"method": "fixed ex-post cohort; equal weight rebalanced at each monthly source endpoint; arithmetic close-to-close; no cashflows or costs",
            "first_month": ordered_months[0], "last_month": ordered_months[-1],
            "interval_count": len(intervals), "cohort_size": len(tickers),
            "source_adj_index_final": round(nav_adj, 10),
            "source_close_index_final": round(nav_close, 10),
            "intervals": intervals}


def evaluate(w: dict, x: dict, manifest: dict, db: sqlite3.Connection) -> dict:
    if (w.get("schema") != "MERIDYEN_PHASE25W_RESEARCH_PILOT_FAIL_CLOSED_V1"
            or w.get("research_only_pilot_selected") != 25
            or len(w.get("pilot_candidates", [])) != 25
            or w.get("conflict_rows") != 464
            or w.get("conflict_rows_canonically_resolved") != 0
            or len(w.get("conflict_quarantine_rows", [])) != 464
            or w.get("canonical_accepted_securities_proven") != 0):
        raise ValueError("Phase25W research-only or quarantine contract changed")
    if (x.get("schema") != "phase25x_research_evidence_matrix_v1"
            or x.get("canonical_accepted_securities_proven") != 0
            or x.get("wf9_status") != "BLOCKED"
            or any(r.get("canonical_admitted") is not False for r in x.get("candidates", []))):
        raise ValueError("Phase25X zero-canonical gate changed")
    if (manifest.get("schema") != "MERIDYEN_PHASE25Q_VERSIONED_RESEARCH_STAGING_V1"
            or manifest.get("staging_version") != w.get("source_staging_version")
            or manifest.get("source_price_sha256") != w.get("source_price_sha256")
            or manifest.get("canonical_ready") is not False):
        raise ValueError("staging version or research-only gate changed")
    collisions = {r["ticker"] for r in w["conflict_quarantine_rows"]}
    series = {}
    for item in w["pilot_candidates"]:
        ticker, sid = item["ticker"], str(item["simfin_id"])
        if ticker in collisions or ticker in series or item["source_price_rows"] != 438 or item["months_with_ticker_source_listing"] != 21:
            raise ValueError("pilot membership/identity/coverage conflict")
        bars = db.execute("SELECT trade_date,source_adj_close,source_close FROM source_daily_price WHERE simfin_id=? AND ticker=? ORDER BY trade_date", (sid, ticker)).fetchall()
        series[ticker] = month_end_series(bars, item["source_price_rows"])
    path = equal_weight_path(series)
    return {"schema": SCHEMA, "status": "EXPERIMENTAL_RESEARCH_ONLY_NOT_CANONICAL_PERFORMANCE",
            "source_staging_version": w["source_staging_version"], "cohort_tickers": sorted(series),
            "research_only_cohort_size": 25, "conflict_rows_still_quarantined": 464,
            "canonical_accepted_securities": 0, "wf9_executed": False,
            "backtest": path, "limitations": list(LIMITATIONS),
            "source_files_modified": False, "operational_db_opened": False, "production_models_modified": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase25w", type=Path, required=True)
    parser.add_argument("--phase25x", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    private_root = (Path(os.environ["LOCALAPPDATA"]) / "S153ResearchTerminal" / "runtime").resolve()
    if not args.out.resolve().is_relative_to(private_root / "phase25y") or args.out.exists() or args.out.is_symlink():
        parser.error("output must be a new private phase25y file")
    if any(not p.resolve().is_relative_to(private_root) for p in (args.phase25w, args.phase25x, args.manifest)):
        parser.error("all inputs must be existing private runtime files")
    source_paths = (args.phase25w, args.phase25x, args.manifest)
    before = {str(p): digest(p) for p in source_paths}
    w, x, manifest = [read_json(p) for p in source_paths]
    stage = Path(manifest["staging_db"])
    if stage.is_symlink() or not stage.is_file() or not stage.resolve().is_relative_to(private_root):
        parser.error("expected existing private staging SQLite")
    with closing(sqlite3.connect(stage.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        result = evaluate(w, x, manifest, db)
    if before != {str(p): digest(p) for p in source_paths}:
        raise RuntimeError("input report changed during audit")
    result["input_sha256"] = before
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    b = result["backtest"]
    print(json.dumps({"status": result["status"], "cohort": b["cohort_size"],
                      "intervals": b["interval_count"], "source_adj_index_final": b["source_adj_index_final"],
                      "canonical": 0, "report": str(args.out)}))


if __name__ == "__main__":
    main()
