"""Phase25g — factor-implied cash diagnostics for Phase25f source anomalies.

All computed numbers are conditional *research diagnostics*, not proof of
dividend, split, adjusted-price correctness, historical identity, or PIT.
No SEC/network requests, database changes, new vendor prices, or training.
"""
from __future__ import annotations
import argparse
import csv
from datetime import date
import hashlib
import io
import json
import math
import os
from pathlib import Path

from scripts.phase25f_p1_official_evidence_worklist import SCHEMA as F_SCHEMA
from scripts.phase25b_simfin_distinct_daily_depth_audit import WINDOW

SCHEMA = "MERIDYEN_PHASE25G_SOURCE_FACTOR_CASH_IMPLICATION_DIAG_V1"
F_STATUS = "P1_INDEPENDENT_CORPORATE_ACTION_EVIDENCE_REVIEW_NEEDED_NOT_CERTIFIED"
COLS = [
    "SimFinId","ticker","source_event_kind","source_event_months",
    "source_before_date","source_after_date","calendar_gap_days",
    "source_before_raw_close","source_after_raw_close",
    "source_before_adj_close","source_after_adj_close",
    "source_before_factor","source_after_factor",
    "source_factor_pct_change_signed",
    "conditional_implied_single_cash_per_share",
    "source_raw_close_return_pct",
    "source_adjusted_close_return_pct",
    "source_original_anomaly_pct",
    "research_classification",
    "official_corporate_action_evidence_independently_confirmed",
    "canonical_adjusted_price_approved",
]


def _read(path:Path)->tuple[dict,str]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("PHASE25F_REPORT_NOT_FOUND")
    data=path.read_bytes()
    payload=json.loads(data)
    if not isinstance(payload,dict):
        raise ValueError("PHASE25F_NOT_OBJECT")
    return payload,hashlib.sha256(data).hexdigest()


def _number(x):
    return isinstance(x,(float,int)) and not isinstance(x,bool) and math.isfinite(x) and x>0


def _day(s):
    if not isinstance(s,str) or len(s)!=10 or not WINDOW["start"]<=s<=WINDOW["end"]:
        raise ValueError("SOURCE_DATE_OUTSIDE_WINDOW")
    return date.fromisoformat(s)


def _safe_csv(x):
    s=str(x) if x is not None else ""
    return "'"+s if s.lstrip().startswith(("=","+","-","@","\t","\r")) else s


def analyze(path:Path):
    report,sha=_read(path)
    if (report.get("schema")!=F_SCHEMA or report.get("status")!=F_STATUS
        or report.get("window")!=WINDOW
        or report.get("P1_SimFinIds")!=6
        or report.get("P1_dated_source_events")!=15
        or report.get("separate_independent_evidence_obtained") is not False
        or report.get("official_exchange_or_issuer_corporate_action_verified")!=0
        or report.get("historical_issuer_CIK_verified")!=0
        or report.get("adjusted_price_validated")!=0
        or report.get("canonical_backtest_eligible_securities")!=0
        or report.get("original_sources_modified") is not False
        or report.get("operational_DB_modified") is not False
        or report.get("models_modified") is not False
        or report.get("network_requests")!=0
        or report.get("paid_API_requests")!=0
        or report.get("model_training_performed") is not False):
        raise ValueError("PHASE25F_UNSAFE_OR_UNEXPECTED_REPORT")
    rows=report.get("review_rows")
    if not isinstance(rows,list) or len(rows)!=15:
        raise ValueError("PHASE25F_EVENT_COUNT_MISMATCH")
    records=[]
    tickers={}
    observations=set()
    for r in rows:
        sid=str(r.get("SimFinId","")).strip()
        ticker=r.get("ticker")
        kind=r.get("source_event_kind")
        if not sid or not isinstance(ticker,str) or not ticker:
            raise ValueError("PHASE25F_SOURCE_ID_INVALID")
        if ticker in tickers and tickers[ticker]!=sid:
            raise ValueError("TICKER_COLLISION_ID_AMBIGUOUS")
        tickers[ticker]=sid
        if kind not in {
            "SOURCE_FACTOR_WITHIN_MONTH_RANGE_5PCT",
            "SOURCE_FACTOR_MONTH_BOUNDARY_5PCT",
            "SOURCE_ADJ_CLOSE_MONTH_BOUNDARY_MOVE_50PCT",
        }:
            raise ValueError("SOURCE_EVENT_TYPE_INVALID")
        d0,d1=_day(r.get("source_first_date")),_day(r.get("source_last_date"))
        if d0==d1:
            raise ValueError("SOURCE_EVENT_SAME_DATE")
        p0,a0=r.get("source_first_raw_close"),r.get("source_first_adj_close")
        p1,a1=r.get("source_last_raw_close"),r.get("source_last_adj_close")
        if not all(_number(v) for v in (p0,a0,p1,a1)):
            raise ValueError("SOURCE_PRICE_NOT_VALID")
        # Source min/max factor observations can be in reverse date order.
        if d0<=d1:
            before,after=(d0,p0,a0),(d1,p1,a1)
        else:
            before,after=(d1,p1,a1),(d0,p0,a0)
        metric=r.get("factor_range_pct_or_change_pct_or_adjusted_move_pct")
        if not isinstance(metric,(float,int)) or isinstance(metric,bool) or not math.isfinite(metric):
            raise ValueError("SOURCE_METRIC_NOT_VALID")
        key=(sid,kind,r.get("source_months"),str(before[0]),str(after[0]))
        if key in observations:
            raise ValueError("DUPLICATE_SOURCE_EVENT_REVIEW_ROW")
        observations.add(key)
        fbefore=before[1]/before[2]
        fafter=after[1]/after[2]
        # Formula assumes a single cash action, identical share/ADR basis,
        # source-adjustment methodology and NO other corporate action.
        # It is diagnostic ONLY, even when coincidentally matching cash D.
        implied=before[1]*(1-fafter/fbefore)
        result={
            "SimFinId":sid,
            "ticker":ticker,
            "source_event_kind":kind,
            "source_event_months":r.get("source_months"),
            "source_before_date":before[0].isoformat(),
            "source_after_date":after[0].isoformat(),
            "calendar_gap_days":(after[0]-before[0]).days,
            "source_before_raw_close":before[1],
            "source_after_raw_close":after[1],
            "source_before_adj_close":before[2],
            "source_after_adj_close":after[2],
            "source_before_factor":round(fbefore,9),
            "source_after_factor":round(fafter,9),
            "source_factor_pct_change_signed":round(100*(fafter/fbefore-1),5),
            "conditional_implied_single_cash_per_share":round(implied,6),
            "source_raw_close_return_pct":round(100*(after[1]/before[1]-1),5),
            "source_adjusted_close_return_pct":round(100*(after[2]/before[2]-1),5),
            "source_original_anomaly_pct":metric,
            "research_classification":"SOURCE_RATIO_DIAGNOSTIC_NO_OFFICIAL_MATCH",
            "official_corporate_action_evidence_independently_confirmed":False,
            "canonical_adjusted_price_approved":False,
        }
        records.append(result)
    if len(tickers)!=6:
        raise ValueError("PHASE25F_EXPECTED_P1_TICKER_COUNT_CHANGED")
    per_ticker={}
    for name in sorted(tickers):
        selected=[x for x in records if x["ticker"]==name]
        expected=report.get("P1_ticker_event_date_ranges",{}).get(name,{})
        if (len(selected)!=expected.get("source_events")
            or min(min(x["source_before_date"],x["source_after_date"]) for x in selected)!=expected.get("first_source_date")
            or max(max(x["source_before_date"],x["source_after_date"]) for x in selected)!=expected.get("last_source_date")):
            raise ValueError("PHASE25F_TICKER_DATE_BOUNDS_MISMATCH")
        per_ticker[name]=len(selected)
    return {
        "schema":SCHEMA,
        "status":"SOURCE_FACTOR_CASH_IMPLICATIONS_RESEARCH_ONLY_NOT_OFFICIAL_VERIFICATION",
        "phase25f_report_SHA256":sha,
        "source_price_SHA256":report.get("source_price_SHA256"),
        "period":WINDOW,
        "p1_tickers":sorted(tickers),
        "p1_source_event_rows":len(records),
        "events_by_ticker":per_ticker,
        "source_math":records,
        "warnings":[
            "Source factor = raw_close / source adjusted_close.",
            "Implied D = raw_before * (1 - factor_after / factor_before); single-cash-event assumption, NOT official distribution evidence.",
            "These paired source observations are NOT necessarily adjacent exchange trading sessions.",
            "Do NOT calculate or approve canonical returns without adjusted price, independent action, CIK PIT and delisting verification.",
        ],
        "independent_corporate_actions_matched":0,
        "vendor_adjustment_methodology_verified":False,
        "split_events_certified":0,
        "dividend_events_certified":0,
        "canonical_backtest_eligible_securities":0,
        "source_files_modified":False,
        "production_DB_modified":False,
        "SEC_records_modified":False,
        "models_modified":False,
        "network_requests":0,
        "paid_API_requests":0,
        "training_performed":False,
    }


def _write(path:Path,text:str):
    if path.is_symlink() or path.with_name(path.name+".tmp").is_symlink():
        raise ValueError("OUTPUT_IS_SYMLINK")
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+".tmp")
    temp.write_text(text,encoding="utf-8")
    temp.replace(path)


def main():
    root=Path(os.environ.get("LOCALAPPDATA") or str(Path.home()))/"S153ResearchTerminal/runtime"
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase25f",type=Path,
                        default=root/"phase25f/p1_independent_source_review_queue.json")
    parser.add_argument("--out",type=Path,
                        default=root/"phase25g/p1_source_factor_cash_diagnostic.json")
    parser.add_argument("--csv",type=Path,
                        default=root/"phase25g/p1_source_factor_cash_diagnostic.csv")
    args=parser.parse_args()
    try:
        outputs={args.out.resolve(),args.csv.resolve()}
        if len(outputs)!=2 or args.phase25f.resolve() in outputs:
            raise ValueError("OUTPUT_OVERLAPS_SOURCE")
        results=analyze(args.phase25f)
        buff=io.StringIO(newline="")
        writer=csv.DictWriter(buff,fieldnames=COLS,lineterminator="\n")
        writer.writeheader()
        for rec in results["source_math"]:
            writer.writerow({k:_safe_csv(rec[k]) for k in COLS})
        _write(args.out,json.dumps(results,ensure_ascii=False,indent=2)+"\n")
        _write(args.csv,buff.getvalue())
    except (ValueError,TypeError,KeyError,OSError,UnicodeError,ZeroDivisionError):
        print("PHASE25G_BLOCKED: UNEXPECTED_SOURCE_REPORT_OR_PRICE_OBSERVATION")
        return 2
    print(json.dumps({
        "status":results["status"],
        "P1_hisse":len(results["p1_tickers"]),
        "gercek_kaynak_olay_kaydi":results["p1_source_event_rows"],
        "events_by_ticker":results["events_by_ticker"],
        "official_cash_amount_reconciliation_completed":False,
        "corporate_action_verified":0,
        "canonical_backtest_approved":0,
        "report_json":str(args.out),"report_csv":str(args.csv),
        "database_modified":False,
    },ensure_ascii=False,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
