"""Phase25e: dated, source-only research packets for Phase25d anomaly worklist.

Fail-closed: no proof of a split, dividend, SEC publication timestamp,
historic ticker-to-CIK identity, trading-session calendar or canonical
returns. Does NOT change operational DB, prices or S15.3/S16 models.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import json
import math
import os
from pathlib import Path

from scripts.phase21_simfin_price_source_audit import _file_sha256, _reader
from scripts.phase22_simfin_ohlc_monthly_qa import _classify_ohlc, _monthly_pit, input_text
from scripts.phase25b_simfin_distinct_daily_depth_audit import PER_MONTH_KEYS, WINDOW
from scripts.phase25d_simfin_adjustment_review_queue import (
    SCHEMA as D_SCHEMA, analyze as review_queue_analyze,
)

SCHEMA = "MERIDYEN_PHASE25E_DATED_SIMFIN_PRICE_ANOMALY_SOURCE_EVIDENCE_V1"
D_STATUS = "UNIQUE_SOURCE_FACTOR_AND_RETURN_ALERT_WORKLIST_RESEARCH_ONLY_NOT_CANONICAL"


def _load_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError("PRIVATE_PHASE25D_REPORT_NOT_FOUND")
    result = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError("NOT_A_JSON_OBJECT")
    return result


def _row(date_value: date, close: float, adjusted: float) -> dict:
    return {
        "source_date": date_value.isoformat(),
        # Preserve exact source float values for comparisons with Phase25c.
        # Display-only rounded values would silently change 5% threshold edges.
        "raw_close": close,
        "source_adj_close": adjusted,
        "source_close_to_adjusted_factor": close/adjusted,
    }


def _month():
    return {
        "first": None, "last": None,
        "minimum": None, "maximum": None,
        "n": 0, "dates": set(),
    }


def _factor(rec):
    return rec["raw_close"] / rec["source_adj_close"]


def _add(acc: dict, rec: dict):
    day = date.fromisoformat(rec["source_date"]).toordinal()
    if day in acc["dates"]:
        raise ValueError("QUALIFIED_SIMFINID_DATE_DUPLICATE_NOT_SUPPORTED")
    acc["dates"].add(day)
    if acc["first"] is None or day < date.fromisoformat(acc["first"]["source_date"]).toordinal():
        acc["first"] = rec
    if acc["last"] is None or day > date.fromisoformat(acc["last"]["source_date"]).toordinal():
        acc["last"] = rec
    if acc["minimum"] is None or _factor(rec) < _factor(acc["minimum"]):
        acc["minimum"] = rec
    if acc["maximum"] is None or _factor(rec) > _factor(acc["maximum"]):
        acc["maximum"] = rec
    acc["n"] += 1


def audit(source: Path, phase25b: Path, phase25c: Path, phase25d: Path,
          pit_dir: Path) -> dict:
    expected, queue = review_queue_analyze(phase25b, phase25c)
    prior = _load_json(phase25d)
    if (
        prior.get("schema") != D_SCHEMA or prior.get("status") != D_STATUS
        or prior.get("source_price_SHA256") != expected.get("source_price_SHA256")
        or prior.get("SimFinIds_reviewed") != expected.get("SimFinIds_reviewed")
        or prior.get("metrics") != expected.get("metrics")
        or prior.get("canonical_backtest_eligible_securities") != 0
        or prior.get("database_modified") is not False
        or prior.get("source_price_modified") is not False
        or prior.get("training_performed") is not False
        or prior.get("review_queue") != queue
    ):
        raise ValueError("PHASE25D_REPORT_OR_QUEUE_PROVENANCE_MISMATCH")
    if source.is_symlink() or not source.is_file():
        raise ValueError("SIMFIN_CSV_NOT_FOUND")
    sha = _file_sha256(source)
    if sha != expected["source_price_SHA256"]:
        raise ValueError("SIMFIN_SOURCE_SHA256_MISMATCH")
    listing = _monthly_pit(
        pit_dir, date.fromisoformat(WINDOW["start"]), date.fromisoformat(WINDOW["end"])
    )
    if set(listing) != set(PER_MONTH_KEYS):
        raise ValueError("PIT_LISTING_ARCHIVE_MONTHS_MISMATCH")

    targets = {str(row["SimFinId"]): row for row in queue}
    monthly = {sid: {} for sid in targets}
    rows = Counter()
    with input_text(source) as handle:
        reader = _reader(handle)
        cols0 = {str(x).strip().lower(): x for x in reader.fieldnames or []}
        def column(*keys):
            return next((cols0[k.lower()] for k in keys if k.lower() in cols0), None)
        cols = {
            "ticker":column("Ticker","Symbol"), "id":column("SimFinId"),
            "date":column("Date"), "open":column("Open"),"high":column("High"),
            "low":column("Low"), "close":column("Close"),
            "adjusted":column("Adj. Close","Adjusted Close","Adj Close"),
        }
        if any(v is None for v in cols.values()):
            raise ValueError("SIMFIN_REQUIRED_SOURCE_COLUMNS_MISSING")
        for item in reader:
            sid = str(item.get(cols["id"]) or "").strip()
            target = targets.get(sid)
            if target is None:
                continue
            ds = str(item.get(cols["date"]) or "").strip()
            sym = str(item.get(cols["ticker"]) or "").strip().upper()
            if (
                len(ds) != 10 or not WINDOW["start"] <= ds <= WINDOW["end"]
                or sym != target["ticker"] or sym not in listing.get(ds[:7], set())
            ):
                continue
            try:
                day = date.fromisoformat(ds)
            except ValueError:
                continue
            if _classify_ohlc(item, cols) != "VALID":
                continue
            try:
                close = float(item.get(cols["close"]) or "")
                adjusted = float(item.get(cols["adjusted"]) or "")
            except (ValueError, TypeError):
                continue
            if not (math.isfinite(close) and close > 0
                    and math.isfinite(adjusted) and adjusted > 0):
                continue
            rec = _row(day, close, adjusted)
            acc = monthly[sid].setdefault(ds[:7], _month())
            _add(acc, rec)
            rows[sid] += 1

    source_events = []
    per_candidate = []
    classes = Counter()
    priorities = Counter()
    for sid, target in sorted(targets.items()):
        all_months = monthly[sid]
        if (
            set(all_months) != set(PER_MONTH_KEYS)
            or rows[sid] != target["qualified_source_rows"]
        ):
            raise ValueError("PHASE25D_SOURCE_ROWS_OR_MONTHS_CHANGED_" + sid)
        candidate_events = []
        intra = boundary = extreme = 0
        for m in PER_MONTH_KEYS:
            acc = all_months[m]
            min_factor = _factor(acc["minimum"])
            max_factor = _factor(acc["maximum"])
            jump = max_factor/min_factor - 1
            if jump >= .05:
                intra += 1
                candidate_events.append({
                    "kind": "SOURCE_FACTOR_WITHIN_MONTH_RANGE_5PCT",
                    "month": m, "factor_range_pct": round(jump*100, 5),
                    "observations": [acc["minimum"], acc["maximum"]],
                })
        for previous, current in zip(PER_MONTH_KEYS, PER_MONTH_KEYS[1:]):
            prev = all_months[previous]["last"]
            nxt = all_months[current]["first"]
            fac = _factor(nxt)/_factor(prev)
            change = max(fac, 1/fac)-1
            if change >= .05:
                boundary += 1
                candidate_events.append({
                    "kind": "SOURCE_FACTOR_MONTH_BOUNDARY_5PCT",
                    "months": [previous, current],
                    "absolute_factor_ratio_change_pct": round(change*100, 5),
                    "observations": [prev, nxt],
                })
            ret = nxt["source_adj_close"]/prev["source_adj_close"]-1
            if abs(ret) >= .5:
                extreme += 1
                candidate_events.append({
                    "kind": "SOURCE_ADJ_CLOSE_MONTH_BOUNDARY_MOVE_50PCT",
                    "months": [previous, current],
                    "signed_source_adj_close_move_pct": round(ret*100, 5),
                    "observations": [prev, nxt],
                })
        if (
            intra != target["intra_month_factor_5pct_months"]
            or boundary != target["factor_5pct_month_boundary_events"]
            or extreme != target["extreme_adj_month_boundary_moves"]
        ):
            raise ValueError("PHASE25C_EVENT_COUNTS_RECONCILIATION_FAILED_" + sid)
        if not candidate_events:
            raise ValueError("PHASE25D_ALERT_WITHOUT_DATED_EVENT_" + sid)
        priorities[target["priority"]] += 1
        for ev in candidate_events:
            classes[ev["kind"]] += 1
            source_events.append({
                "SimFinId": sid,
                "ticker": target["ticker"],
                "priority": target["priority"],
                "present_day_CIK_candidate_NOT_verified":
                    target["present_day_CIK_candidate_NOT_verified"],
                **ev,
                "split_or_dividend_proven": False,
                "historical_CIK_certified": False,
            })
        per_candidate.append({
            "SimFinId": sid, "ticker": target["ticker"],
            "priority": target["priority"], "intra_month_ranges": intra,
            "factor_month_boundaries": boundary,
            "extreme_adjusted_month_boundaries": extreme,
            "dated_source_event_count": len(candidate_events),
            "independent_corporate_action_evidence_obtained": False,
        })
    if len(per_candidate) != expected["unique_review_candidates"]:
        raise ValueError("PHASE25D_QUEUE_COUNT_CHANGED")
    if (
        classes["SOURCE_FACTOR_WITHIN_MONTH_RANGE_5PCT"]
            != expected["metrics"]["intra_month_factor_months"]
        or classes["SOURCE_FACTOR_MONTH_BOUNDARY_5PCT"]
            != expected["metrics"]["month_boundary_factor_events"]
        or classes["SOURCE_ADJ_CLOSE_MONTH_BOUNDARY_MOVE_50PCT"]
            != expected["metrics"]["extreme_adjusted_boundary_events"]
    ):
        raise ValueError("PHASE25C_EVENT_TOTALS_RECONCILIATION_FAILED")
    p1 = [r for r in per_candidate if r["priority"] == "P1_MULTI_ALERT"]
    return {
        "schema": SCHEMA,
        "status": "DATED_SOURCE_PRICE_ANOMALIES_RESEARCH_ONLY_NOT_CANONICAL",
        "window": WINDOW,
        "source_SHA256": sha,
        "candidate_SimFinIds": len(per_candidate),
        "event_counts": dict(sorted(classes.items())),
        "priority_counts": dict(sorted(priorities.items())),
        "P1_candidates": p1,
        "per_candidate": per_candidate,
        "source_only_event_observations": source_events,
        "required_independent_review": [
            "Exchange/issuer actual split or dividend event and effective/ex dates",
            "SEC/issuer historical legal entity identity, time-varying CIK/FIGI",
            "Publisher/source adjusted close definition and independent verification",
            "Exchange trading calendar, delisting outcomes and stale data",
        ],
        "limitations": [
            "Min/max factor points are not asserted to identify the exact corporate-action date.",
            "Adjacent months' nearest quoted prices do not independently prove a split, dividend or trading session.",
            "No lookahead-safe canonical prices or returns are authorized by this packet.",
        ],
        "split_verified": 0, "dividend_verified": 0,
        "adjusted_prices_certified": 0,
        "historical_identity_certifications": 0,
        "canonical_backtest_eligible_securities": 0,
        "database_modified": False, "source_price_modified": False,
        "SEC_records_modified": False, "models_modified": False,
        "model_training_performed": False,
        "network_requests": 0, "paid_API_requests": 0,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    root = Path(os.environ.get("LOCALAPPDATA") or str(Path.home())) / (
        "S153ResearchTerminal/runtime"
    )
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--phase25b", type=Path,
                   default=root/"phase25b/simfin_distinct_daily_depth_research.json")
    p.add_argument("--phase25c", type=Path,
                   default=root/"phase25c/simfin_adjustment_factor_source_triage.json")
    p.add_argument("--phase25d", type=Path,
                   default=root/"phase25d/simfin_adjustment_review_worklist.json")
    p.add_argument("--pit-dir", type=Path, default=root/"phase19/pit_staging")
    p.add_argument("--out", type=Path,
                   default=root/"phase25e/simfin_dated_source_anomaly_packets.json")
    a = p.parse_args()
    try:
        source_paths = {x.resolve() for x in (a.input, a.phase25b, a.phase25c, a.phase25d)}
        if (
            a.out.is_symlink() or a.out.resolve() in source_paths
            or a.pit_dir.resolve() in a.out.resolve().parents
        ):
            raise ValueError("OUTPUT_OVERWRITES_SOURCE")
        result = audit(a.input, a.phase25b, a.phase25c, a.phase25d, a.pit_dir)
        a.out.parent.mkdir(parents=True,exist_ok=True)
        temp = a.out.with_name(a.out.name+".tmp")
        if temp.is_symlink():
            raise ValueError("TEMP_REPORT_OUTPUT_SYMLINK")
        temp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        temp.replace(a.out)
    except (OSError, ValueError, TypeError, KeyError, ZeroDivisionError):
        print("PHASE25E_BLOCKED: SOURCE_PROVENANCE_OR_EVENT_RECONCILIATION_FAILED")
        return 2
    print(json.dumps({
        "status": result["status"],
        "unique_review_candidates": result["candidate_SimFinIds"],
        "P1_candidate_count": len(result["P1_candidates"]),
        "P1_tickers": [x["ticker"] for x in result["P1_candidates"]],
        "dated_event_counts": result["event_counts"],
        "split_verified": 0,"dividend_verified":0,"canonical_eligible":0,
        "private_report": str(a.out),"database_modified":False,
    }, ensure_ascii=False,indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
