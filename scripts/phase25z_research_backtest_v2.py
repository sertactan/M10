"""Phase25Z retrospective research sensitivity; never canonical performance."""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
from statistics import median

from scripts.phase25y_research_only_backtest import month_end_series, months, equal_weight_path

SCHEMA = "phase25z_research_backtest_v2"
RISK_LEDGER = [
    {"code": "LOOKAHEAD_EX_POST_COHORT", "level": "BLOCKED", "detail": "Pilot chosen after full-window price coverage and 2026-retrieved lists were visible."},
    {"code": "SURVIVORSHIP_AND_DELISTING", "level": "BLOCKED", "detail": "Missing histories, delisted names and terminal payoffs are not represented by the fixed 25."},
    {"code": "RETROSPECTIVE_MEMBERSHIP", "level": "BLOCKED", "detail": "The 21 historical month lists were retrieved retrospectively, not contemporaneously captured."},
    {"code": "CORPORATE_ACTION_PRICE_FACTORS", "level": "BLOCKED", "detail": "Source adjusted-close factors, dividends, rights and terminal payouts lack independent certification."},
    {"code": "SEC_AVAILABLE_AT", "level": "BLOCKED", "detail": "Accepted time is not demonstrated public or feature ingestion availability; no SEC features enter this arithmetic."},
    {"code": "EXCHANGE_SESSIONS", "level": "PARTIAL", "detail": "Missing dates measured against source-date union only, not an independently certified exchange calendar."},
    {"code": "HISTORICAL_SECTOR", "level": "UNAVAILABLE", "detail": "A dated sector mapping is absent from the bounded research sources; no sector concentration computed."},
]


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing or linked source")
    return json.loads(path.read_text(encoding="utf-8"))


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lo, hi = math.floor(position), math.ceil(position)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (position - lo)


def diagnostics(series: dict[str, dict], all_dates: dict[str, set[str]], baseline: dict) -> dict:
    names = sorted(series)
    keys = months()
    if len(names) != 25 or any(sorted(series[t]) != keys for t in names):
        raise ValueError("Expected exactly 25 complete monthly series")
    source_union = set().union(*all_dates.values())
    if not source_union:
        raise ValueError("No source dates")
    missing_source_dates = {t: len(source_union - all_dates[t]) for t in names}
    endpoint_lags = {}
    for month in keys:
        latest = max(series[t][month]["trade_date"] for t in names)
        endpoint_lags[month] = {t: (latest != series[t][month]["trade_date"]) for t in names}
    lagged = {t: sum(endpoint_lags[m][t] for m in keys) for t in names}
    if baseline.get("cohort_size") != 25 or baseline.get("interval_count") != 20:
        raise ValueError("Phase25Y-A baseline shape changed")
    observed = equal_weight_path(series)
    for k in ("source_adj_index_final", "source_close_index_final"):
        if abs(observed[k] - baseline[k]) > 1e-9:
            raise ValueError("Phase25Y-A baseline does not reproduce")
    nav, winsor_nav, median_nav = 1.0, 1.0, 1.0
    contributions = {t: 0.0 for t in names}
    close_contributions = {t: 0.0 for t in names}
    returns_by_month = []
    per_ticker_returns = {t: [] for t in names}
    for prior, current in zip(keys, keys[1:]):
        adjusted = {t: series[t][current]["adj_close"] / series[t][prior]["adj_close"] - 1 for t in names}
        close = {t: series[t][current]["close"] / series[t][prior]["close"] - 1 for t in names}
        for t in names:
            per_ticker_returns[t].append(adjusted[t])
            contributions[t] += nav * adjusted[t] / 25
            close_contributions[t] += (close[t] - adjusted[t]) / 25  # diagnostic arithmetic spread, not exact index attribution
        vals = list(adjusted.values())
        lo, hi = percentile(vals, 0.05), percentile(vals, 0.95)
        capped = [max(lo, min(hi, v)) for v in vals]
        nav *= 1 + sum(vals) / 25
        winsor_nav *= 1 + sum(capped) / 25
        median_nav *= 1 + median(vals)
        gap = sum(adjusted[t] - close[t] for t in names) / 25
        returns_by_month.append({"from": prior, "to": current,
                                 "adj_minus_close_mean_return": round(gap, 10),
                                 "source_adj_index": round(nav, 10),
                                 "winsor_5_95_index": round(winsor_nav, 10),
                                 "median_index": round(median_nav, 10),
                                 "upper_winsor_cut": round(hi, 10), "lower_winsor_cut": round(lo, 10)})
    if abs(nav - baseline["source_adj_index_final"]) > 1e-9:
        raise ValueError("Final attribution does not tie to baseline")
    if abs(sum(contributions.values()) - (nav - 1)) > 1e-9:
        raise ValueError("Contributions do not tie to index change")
    loo = {}
    for removed in names:
        rest = [t for t in names if t != removed]
        index = 1.0
        for j in range(len(keys) - 1):
            index *= 1 + sum(per_ticker_returns[t][j] for t in rest) / len(rest)
        loo[removed] = {"index_without": round(index, 10), "full_minus_without": round(nav - index, 10)}
    ranks = sorted(names, key=lambda t: abs(loo[t]["full_minus_without"]), reverse=True)
    absolute = {t: abs(contributions[t]) for t in names}
    gross_abs = sum(absolute.values())
    concentration = {"top_one_abs_contribution_share": round(max(absolute.values()) / gross_abs, 10),
                     "top_five_abs_contribution_share": round(sum(sorted(absolute.values(), reverse=True)[:5]) / gross_abs, 10),
                     "abs_contribution_hhi": round(sum((v / gross_abs) ** 2 for v in absolute.values()), 10),
                     "basis": "absolute exact adjusted-index contributions, not market weights"}
    outliers = []
    for j, (prior, current) in enumerate(zip(keys, keys[1:])):
        for t in names:
            outliers.append({"ticker": t, "from": prior, "to": current,
                             "source_adj_return": round(per_ticker_returns[t][j], 10),
                             "equal_weight_one_month_return_component": round(per_ticker_returns[t][j] / 25, 10)})
    outliers.sort(key=lambda r: abs(r["equal_weight_one_month_return_component"]), reverse=True)
    close_adj = sorted(returns_by_month, key=lambda r: abs(r["adj_minus_close_mean_return"]), reverse=True)
    return {"source_date_union_count": len(source_union), "source_first_date": min(source_union), "source_last_date": max(source_union),
            "missing_dates_against_source_union": missing_source_dates, "lagged_month_endpoints_against_source_cohort": lagged,
            "source_calendar_certified": False, "historical_sector_concentration": None,
            "stock_concentration": concentration,
            "per_ticker_source_coverage": {t: {"rows": len(all_dates[t]), "first": min(all_dates[t]), "last": max(all_dates[t])} for t in names},
            "rebalance_assumption": "equal weights reset at each monthly source endpoint; no execution/cost model",
            "source_adj_index_final": baseline["source_adj_index_final"],
            "source_close_index_final": baseline["source_close_index_final"],
            "winsor_5_95_index_final": round(winsor_nav, 10), "median_index_final": round(median_nav, 10),
            "alternative_estimators_are_not_trade_returns": True,
            "exact_rebalanced_source_adj_index_contribution": {t: round(contributions[t], 10) for t in names},
            "contribution_sum": round(sum(contributions.values()), 10),
            "leave_one_out": loo, "most_influential_leave_one_out": ranks[:10],
            "largest_single_name_month_moves": outliers[:15],
            "largest_monthly_adj_minus_close_gaps": close_adj[:10],
            "monthly_diagnostics": returns_by_month}


def evaluate(w: dict, x: dict, y: dict, manifest: dict, db: sqlite3.Connection) -> dict:
    if (w.get("schema") != "MERIDYEN_PHASE25W_RESEARCH_PILOT_FAIL_CLOSED_V1"
            or w.get("research_only_pilot_selected") != 25 or len(w.get("pilot_candidates", [])) != 25
            or w.get("conflict_rows") != 464 or len(w.get("conflict_quarantine_rows", [])) != 464
            or w.get("conflict_rows_canonically_resolved") != 0 or w.get("canonical_accepted_securities_proven") != 0):
        raise ValueError("Phase25W research-only gate changed")
    if (x.get("schema") != "phase25x_research_evidence_matrix_v1"
            or x.get("canonical_accepted_securities_proven") != 0 or x.get("canonical_accepted_security_dates_proven") != 0
            or x.get("wf9_status") != "BLOCKED"):
        raise ValueError("Phase25X canonical gate changed")
    if (y.get("schema") != "phase25y_experimental_research_backtest_v1"
            or y.get("status") != "EXPERIMENTAL_RESEARCH_ONLY_NOT_CANONICAL_PERFORMANCE"
            or y.get("canonical_accepted_securities") != 0 or y.get("wf9_executed") is not False
            or y.get("source_staging_version") != w.get("source_staging_version")):
        raise ValueError("Phase25Y-A experimental baseline changed")
    if (manifest.get("schema") != "MERIDYEN_PHASE25Q_VERSIONED_RESEARCH_STAGING_V1"
            or manifest.get("staging_version") != w.get("source_staging_version")
            or manifest.get("source_price_sha256") != w.get("source_price_sha256")
            or manifest.get("canonical_ready") is not False):
        raise ValueError("Source stage contract changed")
    collision_symbols = {r["ticker"] for r in w["conflict_quarantine_rows"]}
    series, all_dates = {}, {}
    for item in w["pilot_candidates"]:
        ticker = item["ticker"]
        if ticker in series or ticker in collision_symbols or item["source_price_rows"] != 438:
            raise ValueError("Pilot duplicate, collision or coverage mismatch")
        bars = db.execute("SELECT trade_date,source_adj_close,source_close FROM source_daily_price WHERE simfin_id=? AND ticker=? ORDER BY trade_date", (str(item["simfin_id"]), ticker)).fetchall()
        all_dates[ticker] = {r[0] for r in bars}
        series[ticker] = month_end_series(bars, 438)
    result = diagnostics(series, all_dates, y["backtest"])
    return {"schema": SCHEMA, "status": "EXPERIMENTAL_RESEARCH_ONLY", "period": w["period"],
            "cohort_tickers": sorted(series), "pilot_size": 25, "source_staging_version": w["source_staging_version"],
            "diagnostics": result, "risk_ledger": RISK_LEDGER,
            "canonical_accepted_securities": 0, "canonical_accepted_security_dates": 0,
            "wf9_status": "BLOCKED", "learning_v3_status": "NOT_TRAINED",
            "research_mode": "ENABLED_EXPERIMENTAL_ONLY", "canonical_mode": "BLOCKED_MISSING_ALL_REQUIRED_EVIDENCE",
            "production_db_opened": False, "source_modified": False}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("phase25w", "phase25x", "phase25y_a", "manifest", "out"):
        p.add_argument("--" + name.replace("_", "-"), type=Path, required=True)
    a = p.parse_args()
    root = (Path(os.environ["LOCALAPPDATA"]) / "S153ResearchTerminal" / "runtime").resolve()
    sources = (a.phase25w, a.phase25x, a.phase25y_a, a.manifest)
    if any(not source.resolve().is_relative_to(root) for source in sources):
        p.error("Inputs must remain under private runtime")
    if not a.out.resolve().is_relative_to(root / "phase25z") or a.out.exists() or a.out.is_symlink():
        p.error("Output must be new and private")
    before = {str(source): digest(source) for source in sources}
    w, x, y, manifest = [load(source) for source in sources]
    stage = Path(manifest["staging_db"])
    if stage.is_symlink() or not stage.is_file() or not stage.resolve().is_relative_to(root):
        p.error("Existing private stage missing")
    with closing(sqlite3.connect(stage.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        result = evaluate(w, x, y, manifest, db)
    if before != {str(source): digest(source) for source in sources}:
        raise RuntimeError("Input changed during audit")
    result["input_sha256"] = before
    result["source_price_sha256"] = manifest["source_price_sha256"]
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"status": result["status"], "pilot": 25,
                      "adjusted_index": result["diagnostics"]["source_adj_index_final"],
                      "canonical": 0, "report": str(a.out)}))


if __name__ == "__main__":
    main()
