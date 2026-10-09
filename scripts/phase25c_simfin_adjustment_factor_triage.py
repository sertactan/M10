"""Phase25c — SimFin source Adj. Close factor candidate triage (read-only).

Analyze the original unmodified SimFin CSV/ZIP for the Phase25b research
cohort: within-month close/adjusted-close factor range and month-boundary
changes. A ratio change is a *candidate* requiring split/dividend/source
verification, never proof of an actual corporate action or adjusted return.
No market-data requests, DB writes, trained models, PIT approval.
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
from scripts.phase22_simfin_ohlc_monthly_qa import (
    _classify_ohlc, input_text, _monthly_pit,
)
from scripts.phase25b_simfin_distinct_daily_depth_audit import (
    SCHEMA as B_SCHEMA, WINDOW, PER_MONTH_KEYS,
)

SCHEMA = "MERIDYEN_PHASE25C_SIMFIN_ADJUSTMENT_FACTOR_CANDIDATES_V1"
B_STATUS = "DISTINCT_SIMFINID_DATE_COUNTS_VERIFIED_RESEARCH_ONLY_NOT_PIT"
MAX_EXAMPLES = 20
FACTOR_THRESHOLDS = (0.02, 0.05, 0.10, 0.25)


def _private_json(path: Path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("PRIVATE_SOURCE_REPORT_MISSING")
    return json.loads(path.read_text(encoding="utf-8"))


def _prior(path: Path):
    doc = _private_json(path)
    if (doc.get("schema") != B_SCHEMA
        or doc.get("status") != B_STATUS
        or doc.get("window") != WINDOW
        or doc.get("canonical_eligible") != 0
        or doc.get("historical_SimFinId_CIK_certifications") != 0
        or doc.get("price_adjustment_certifications") != 0
        or doc.get("operational_DB_modified") is not False
        or doc.get("source_file_modified") is not False
        or doc.get("model_training_performed") is not False):
        raise ValueError("PRIOR_PHASE25B_NOT_RESEARCH_SAFE")
    records = doc.get("candidate_depth_records")
    if (not isinstance(records, list)
        or len(records) != doc.get("phase25a_prior_candidate_21months")
        or len(records) == 0
        or len(records) > 100000):
        raise ValueError("PRIOR_PHASE25B_COHORT_INVALID")
    selected = {}
    for rec in records:
        sid = str(rec.get("SimFinId","")).strip()
        if not sid or sid in selected:
            raise ValueError("PRIOR_PHASE25B_DUPLICATE_SIMFIN_ID")
        if (rec.get("daily_PIT_or_adjustment_certified") is not False
            or len(str(rec.get("ticker","")).strip()) == 0
            or rec.get("candidate_CIK_NOT_verified") in ("", None)):
            raise ValueError("PRIOR_PHASE25B_IDENTITY_PROMOTION_INVALID")
        selected[sid] = rec
    return doc, selected


def _price_cols(fields):
    cm = {str(x).strip().lower(): x for x in (fields or [])}
    def find(*x):
        return next((cm.get(k.lower()) for k in x if cm.get(k.lower())), None)
    columns = {
        "id":find("SimFinId"),
        "ticker":find("Ticker","Symbol"),
        "date":find("Date"),
        "open":find("Open"),
        "high":find("High"),
        "low":find("Low"),
        "close":find("Close"),
        "adjusted":find("Adj. Close","Adjusted Close","Adj Close"),
    }
    if any(col is None for col in columns.values()):
        raise ValueError("SIMFIN_REQUIRED_COLUMNS_NOT_FOUND")
    return columns


def _factor_event(score):
    """Factor ratio is source Close / Adj.Close; comparison is illustrative."""
    return score > 1.05


def _month_accumulator():
    return {"first":None,"last":None,"min_factor":math.inf,
            "max_factor":0.0,"rows":0}


def _add_to_month(a,ordinal,close,adjusted):
    ratio=close/adjusted
    if not math.isfinite(ratio) or ratio<=0:
        raise ValueError("INVALID_SOURCE_ADJUSTMENT_RATIO")
    current=(ordinal,close,adjusted,ratio)
    if a["first"] is None or ordinal<a["first"][0]:
        a["first"]=current
    if a["last"] is None or ordinal>a["last"][0]:
        a["last"]=current
    a["min_factor"]=min(a["min_factor"],ratio)
    a["max_factor"]=max(a["max_factor"],ratio)
    a["rows"]+=1


def analyze(source:Path,pit_dir:Path,phase25b:Path):
    prior, selected=_prior(phase25b)
    if source.is_symlink() or not source.is_file():
        raise ValueError("SIMFIN_SOURCE_NOT_AVAILABLE")
    sha=_file_sha256(source)
    if prior.get("source_price_file_SHA256") != sha:
        raise ValueError("SIMFIN_SOURCE_SHA256_MISMATCH")
    membership=_monthly_pit(
        pit_dir,date.fromisoformat(WINDOW["start"]),date.fromisoformat(WINDOW["end"]))
    if set(membership)!=set(PER_MONTH_KEYS):
        raise ValueError("MONTHLY_SOURCE_ARCHIVE_WINDOW_MISMATCH")
    buckets={sid:{} for sid in selected}
    rows=Counter()
    stats=Counter()
    with input_text(source) as handle:
        reader=_reader(handle)
        cols=_price_cols(reader.fieldnames)
        for item in reader:
            stats["source_rows_read"]+=1
            sid=str(item.get(cols["id"]) or "").strip()
            r=selected.get(sid)
            if r is None:
                continue
            day=str(item.get(cols["date"]) or "").strip()
            ticker=str(item.get(cols["ticker"]) or "").strip().upper()
            if not (len(day)==10 and WINDOW["start"]<=day<=WINDOW["end"]
                    and ticker==r["ticker"]
                    and ticker in membership.get(day[:7],set())):
                continue
            try:
                d=date.fromisoformat(day)
            except ValueError:
                continue
            if _classify_ohlc(item,cols)!="VALID":
                continue
            try:
                adjusted=float(item.get(cols["adjusted"]) or "")
                close=float(item.get(cols["close"]) or "")
            except (ValueError,TypeError):
                continue
            if not (math.isfinite(adjusted) and adjusted>0):
                continue
            a=buckets[sid].setdefault(day[:7],_month_accumulator())
            _add_to_month(a,d.toordinal(),close,adjusted)
            rows[sid]+=1
            stats["qualified_rows"]+=1

    measurements=Counter({
        "candidate_ids_with_factor_5pct_intra_month":0,
        "candidate_ids_with_factor_5pct_month_boundary":0,
        "candidate_ids_with_extreme_adj_month_boundary_return":0,
        "candidate_ids_with_no_detected_5pct_factor_change":0,
        "intra_month_factor_5pct_months":0,
        "factor_5pct_boundary_events":0,
        "extreme_adjusted_month_boundary_moves":0,
    })
    review_samples=[]
    results=[]
    for sid, rec in sorted(selected.items()):
        if rows[sid] != rec.get("valid_ohlc_positive_source_adjusted_rows"):
            raise ValueError("PHASE25B_QUALIFIED_SOURCE_ROWS_CHANGED_"+sid)
        if set(buckets[sid])!=set(PER_MONTH_KEYS):
            raise ValueError("PHASE25B_21_MONTH_PRICE_COVERAGE_CHANGED_"+sid)
        factor_months=[]
        boundary_jumps=[]
        extreme_adj_month_boundaries=[]
        for month in PER_MONTH_KEYS:
            item=buckets[sid][month]
            if item["first"] is None or item["last"] is None:
                raise ValueError("QUALIFIED_MONTH_EMPTY")
            factor_range=item["max_factor"]/item["min_factor"]-1.0
            if factor_range >= .05:
                factor_months.append({"month":month,
                                      "max_over_min_factor_pct":round(100*factor_range,3)})
        for m1,m2 in zip(PER_MONTH_KEYS,PER_MONTH_KEYS[1:]):
            prev=buckets[sid][m1]["last"]
            current=buckets[sid][m2]["first"]
            # Compare factors across nearest qualified *source* month endpoints.
            ratio=current[3]/prev[3]
            jump=max(ratio,1/ratio)-1.0
            if jump>=.05:
                boundary_jumps.append({"prior_month":m1,"next_month":m2,
                                       "absolute_factor_ratio_change_pct":round(100*jump,3)})
            adjusted_return=current[2]/prev[2]-1.0
            if abs(adjusted_return)>=.5:
                extreme_adj_month_boundaries.append({
                    "prior_month":m1,"next_month":m2,
                    "source_adj_close_change_pct":round(100*adjusted_return,3)
                })
        for key,val in (
            ("candidate_ids_with_factor_5pct_intra_month",bool(factor_months)),
            ("candidate_ids_with_factor_5pct_month_boundary",bool(boundary_jumps)),
            ("candidate_ids_with_extreme_adj_month_boundary_return",bool(extreme_adj_month_boundaries)),
            ("candidate_ids_with_no_detected_5pct_factor_change",not (factor_months or boundary_jumps))
        ):
            if val:
                measurements[key]+=1
        measurements["intra_month_factor_5pct_months"]+=len(factor_months)
        measurements["factor_5pct_boundary_events"]+=len(boundary_jumps)
        measurements["extreme_adjusted_month_boundary_moves"]+=len(extreme_adj_month_boundaries)
        if (factor_months or boundary_jumps or extreme_adj_month_boundaries) and len(review_samples)<MAX_EXAMPLES:
            review_samples.append({
                "SimFinId":sid,"ticker":rec["ticker"],
                "intra_month_factor":factor_months[:4],
                "boundary_factor":boundary_jumps[:4],
                "extreme_adjusted_returns":extreme_adj_month_boundaries[:4]
            })
        results.append({
            "SimFinId":sid,
            "ticker":rec["ticker"],
            "candidate_CIK_NOT_historical_verified":rec["candidate_CIK_NOT_verified"],
            "qualified_source_rows":rows[sid],
            "months_covered":len(buckets[sid]),
            "source_close_to_adjusted_factor_range_over_5pct_months":len(factor_months),
            "factor_change_over_5pct_month_boundaries":len(boundary_jumps),
            "extreme_source_adjusted_month_boundary_returns":len(extreme_adj_month_boundaries),
            "corporate_actions_independently_verified":0,
            "adjustment_and_delisting_certified":False,
        })
    if sum(rows.values()) != prior.get("metrics",{}).get("valid_source_rows"):
        raise ValueError("PHASE25B_TOTAL_QUALIFIED_SOURCE_ROWS_MISMATCH")
    return {
        "schema":SCHEMA,
        "status":"SIMFIN_ADJUSTED_PRICE_FACTOR_SOURCE_TRIAGE_NOT_SPLIT_DIVIDEND_PROOF",
        "window":WINDOW,"source_sha256":sha,
        "SimFinIds_reviewed":len(selected),
        "metrics":dict(sorted(measurements.items())),
        "stream_totals":dict(sorted(stats.items())),
        "sample_source_factor_review_candidates":review_samples,
        "candidate_factor_aggregate_records":results,
        "factor_change_rule":"source Close divided by source Adj. Close; 5% threshold is a candidate-screen only",
        "warnings":[
            "Within-month min/max or month-boundary 5% close/adj ratio change is NOT evidence of a specific split or cash dividend.",
            "No independent company action, dividend ex-date, split ratio, vendor adjustment methodology or delisting proceeds evidence acquired.",
            "No explicit exchange holiday-aware calendar or historical CIK/FIGI/share-class PIT verified.",
            "Source Adj. Close and adjusted returns NOT approved for canonical backtest.",
        ],
        "independent_split_events_verified":0,
        "independent_dividend_events_verified":0,
        "certified_adjusted_prices":0,
        "canonical_backtest_eligible_securities":0,
        "database_modified":False,
        "source_price_modified":False,
        "models_modified":False,
        "network_requests":0,
        "paid_API_requests":0,
        "training_performed":False,
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    root=Path(os.environ.get("LOCALAPPDATA") or str(Path.home()))/"S153ResearchTerminal/runtime"
    p.add_argument("--input",type=Path,required=True)
    p.add_argument("--phase25b",type=Path,
                   default=root/"phase25b/simfin_distinct_daily_depth_research.json")
    p.add_argument("--pit-dir",type=Path,default=root/"phase19/pit_staging")
    p.add_argument("--out",type=Path,
                   default=root/"phase25c/simfin_adjustment_factor_source_triage.json")
    a=p.parse_args()
    try:
        out=a.out.resolve()
        if (a.out.is_symlink()
            or out in {a.input.resolve(),a.phase25b.resolve()}
            or a.pit_dir.resolve() in out.parents):
            raise ValueError("OUTPUT_OVERWRITES_INPUT")
        data=analyze(a.input,a.pit_dir,a.phase25b)
        a.out.parent.mkdir(parents=True,exist_ok=True)
        temp=a.out.with_suffix(".json.tmp")
        if temp.is_symlink():
            raise ValueError("OUTPUT_TEMP_UNSAFE")
        temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        temp.replace(a.out)
    except (ValueError,OSError,TypeError,KeyError):
        print("PHASE25C_BLOCKED: SOURCE_OR_PRIOR_AUDIT_INVALID")
        return 2
    print(json.dumps({
        "status":data["status"],
        "SimFinIds_reviewed":data["SimFinIds_reviewed"],
        "factor_5pct_intra_month_candidates":data["metrics"].get(
            "candidate_ids_with_factor_5pct_intra_month",0),
        "factor_5pct_boundary_candidates":data["metrics"].get(
            "candidate_ids_with_factor_5pct_month_boundary",0),
        "extreme_adj_month_boundary_candidates":data["metrics"].get(
            "candidate_ids_with_extreme_adj_month_boundary_return",0),
        "split_verified":0,"dividend_verified":0,
        "certified_adjusted_prices":0,
        "canonical_backtest_eligible_securities":0,
        "report":str(a.out),
        "database_modified":False,
    },ensure_ascii=False,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
