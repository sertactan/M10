"""Phase25d — offline, read-only unique corporate-action research review queue.

Consumes certified-as-research-only Phase25b and Phase25c local JSON reports;
does not infer actual split/dividend from a ratio, certify any adjusted
return, acquire outside evidence, write to operational DB or train a model.
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from scripts.phase25c_simfin_adjustment_factor_triage import SCHEMA as C_SCHEMA
from scripts.phase25b_simfin_distinct_daily_depth_audit import SCHEMA as B_SCHEMA, WINDOW

SCHEMA = "MERIDYEN_PHASE25D_CORPORATE_ACTION_RESEARCH_WORKLIST_V1"
C_STATUS = "SIMFIN_ADJUSTED_PRICE_FACTOR_SOURCE_TRIAGE_NOT_SPLIT_DIVIDEND_PROOF"
B_STATUS = "DISTINCT_SIMFINID_DATE_COUNTS_VERIFIED_RESEARCH_ONLY_NOT_PIT"
COLS = [
    "priority", "SimFinId", "ticker", "present_day_CIK_candidate_NOT_verified",
    "review_class", "flag_types", "intra_month_factor_5pct_months",
    "factor_5pct_month_boundary_events", "extreme_adj_month_boundary_moves",
    "qualified_source_rows", "research_only_NOT_PIT",
]


def _read(path: Path)->dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError("SOURCE_PRIVATE_AUDIT_NOT_FOUND_OR_SYMLINK")
    doc=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc,dict):
        raise ValueError("AUDIT_NOT_JSON_OBJECT")
    return doc


def _nonneg(value,code):
    if isinstance(value,bool) or not isinstance(value,int) or value<0:
        raise ValueError(code)
    return value


def _safe_cell(value):
    """Prevent CSV formula evaluation when viewed in Excel."""
    s=str(value)
    return "'"+s if s.lstrip().startswith(("=","+","-","@","\t","\r")) else s


def _checked_reports(phase25b: Path,phase25c: Path):
    b=_read(phase25b)
    c=_read(phase25c)
    if (b.get("schema")!=B_SCHEMA
        or b.get("status")!=B_STATUS
        or b.get("window")!=WINDOW
        or b.get("canonical_eligible")!=0
        or b.get("historical_SimFinId_CIK_certifications")!=0
        or b.get("price_adjustment_certifications")!=0
        or b.get("operational_DB_modified") is not False
        or b.get("source_file_modified") is not False
        or b.get("model_training_performed") is not False):
        raise ValueError("PHASE25B_NOT_SAFE_RESEARCH_REPORT")
    if (c.get("schema")!=C_SCHEMA
        or c.get("status")!=C_STATUS
        or c.get("window")!=WINDOW
        or c.get("certified_adjusted_prices")!=0
        or c.get("canonical_backtest_eligible_securities")!=0
        or c.get("independent_split_events_verified")!=0
        or c.get("independent_dividend_events_verified")!=0
        or c.get("database_modified") is not False
        or c.get("source_price_modified") is not False
        or c.get("models_modified") is not False
        or c.get("training_performed") is not False
        or c.get("network_requests")!=0
        or c.get("paid_API_requests")!=0):
        raise ValueError("PHASE25C_NOT_SAFE_RESEARCH_REPORT")
    sha=b.get("source_price_file_SHA256")
    if not isinstance(sha,str) or len(sha)!=64 or c.get("source_sha256")!=sha:
        raise ValueError("PHASE25B_25C_SHA256_PROVENANCE_MISMATCH")
    b_records=b.get("candidate_depth_records")
    c_records=c.get("candidate_factor_aggregate_records")
    if (not isinstance(b_records,list)
        or not isinstance(c_records,list)
        or not 0 < len(b_records)==len(c_records)==b.get("phase25a_prior_candidate_21months")==c.get("SimFinIds_reviewed")<=100000):
        raise ValueError("PHASE25B_25C_RECORD_COUNT_MISMATCH")
    return b,c,b_records,c_records


def analyze(phase25b:Path, phase25c:Path)->tuple[dict,list[dict]]:
    b,c,br,cr=_checked_reports(phase25b,phase25c)
    by_id={}
    for r in br:
        sid=str(r.get("SimFinId","")).strip()
        if not sid or sid in by_id or r.get("daily_PIT_or_adjustment_certified") is not False:
            raise ValueError("PHASE25B_DUPLICATE_OR_UNSAFE_ID")
        by_id[sid]=r
    counts=Counter()
    queue=[]
    seen=set()
    for r in cr:
        sid=str(r.get("SimFinId","")).strip()
        if not sid or sid in seen or sid not in by_id:
            raise ValueError("PHASE25C_ID_MISSING_DUPLICATE")
        seen.add(sid)
        old=by_id[sid]
        ticker=r.get("ticker")
        cik=r.get("candidate_CIK_NOT_historical_verified")
        rows=_nonneg(r.get("qualified_source_rows"),"PHASE25C_INVALID_PRICE_ROWS")
        if (ticker != old.get("ticker")
            or cik != old.get("candidate_CIK_NOT_verified")
            or rows!=old.get("valid_ohlc_positive_source_adjusted_rows")
            or r.get("months_covered")!=21
            or r.get("corporate_actions_independently_verified")!=0
            or r.get("adjustment_and_delisting_certified") is not False):
            raise ValueError("PHASE25B_25C_CANDIDATE_PROVENANCE_MISMATCH")
        intra=_nonneg(r.get("source_close_to_adjusted_factor_range_over_5pct_months"),
                      "INVALID_INTRA_MONTH_FACTOR_EVENT_COUNT")
        boundary=_nonneg(r.get("factor_change_over_5pct_month_boundaries"),
                         "INVALID_MONTH_BOUNDARY_FACTOR_EVENT_COUNT")
        extreme=_nonneg(r.get("extreme_source_adjusted_month_boundary_returns"),
                        "INVALID_EXTREME_ADJ_EVENT_COUNT")
        if intra>21 or boundary>20 or extreme>20:
            raise ValueError("IMPOSSIBLE_MONTH_FACTOR_EVENT_COUNTS")
        flags=[]
        if intra:
            counts["ids_with_intra_month_factor_alert"]+=1
            counts["intra_month_factor_months"]+=intra
            flags.append("INTRA_FACTOR_5PCT")
        if boundary:
            counts["ids_with_month_boundary_factor_alert"]+=1
            counts["month_boundary_factor_events"]+=boundary
            flags.append("BOUNDARY_FACTOR_5PCT")
        if extreme:
            counts["ids_with_extreme_adjusted_boundary_move"]+=1
            counts["extreme_adjusted_boundary_events"]+=extreme
            flags.append("EXTREME_ADJ_50PCT")
        if not flags:
            counts["ids_without_these_three_alerts_NOT_certified_clean"]+=1
            continue
        counts["unique_ids_with_one_or_more_alerts"]+=1
        if intra or boundary:
            counts["unique_ids_with_source_factor_alert"]+=1
        if extreme and not (intra or boundary):
            counts["extreme_adjusted_move_only_ids"]+=1
        if len(flags)>=2:
            counts["unique_ids_with_multiple_alert_classes"]+=1
        if len(flags)==3:
            counts["unique_ids_with_all_three_alert_classes"]+=1
        # Simple deterministic triage, not calibrated risk/scoring.
        priority=("P1_MULTI_ALERT" if len(flags)>=2 else
                  "P2_FACTOR_CHANGE" if intra or boundary else
                  "P3_EXTREME_ADJ_RETURN_ONLY")
        counts["priority_"+priority]+=1
        queue.append({
            "priority":priority,
            "SimFinId":sid,
            "ticker":ticker,
            "present_day_CIK_candidate_NOT_verified":cik,
            "review_class":"SOURCE_PRICE_ANOMALY_CANDIDATE_NOT_CORPORATE_ACTION_PROOF",
            "flag_types":"|".join(flags),
            "intra_month_factor_5pct_months":intra,
            "factor_5pct_month_boundary_events":boundary,
            "extreme_adj_month_boundary_moves":extreme,
            "qualified_source_rows":rows,
            "research_only_NOT_PIT":True,
        })
    if len(seen)!=len(br):
        raise ValueError("UNRECONCILED_PHASE25C_IDS")
    metrics=c.get("metrics",{})
    expected={
        "candidate_ids_with_factor_5pct_intra_month":
            counts["ids_with_intra_month_factor_alert"],
        "candidate_ids_with_factor_5pct_month_boundary":
            counts["ids_with_month_boundary_factor_alert"],
        "candidate_ids_with_extreme_adj_month_boundary_return":
            counts["ids_with_extreme_adjusted_boundary_move"],
        "intra_month_factor_5pct_months":counts["intra_month_factor_months"],
        "factor_5pct_boundary_events":counts["month_boundary_factor_events"],
        "extreme_adjusted_month_boundary_moves":counts["extreme_adjusted_boundary_events"],
    }
    for key,count in expected.items():
        if metrics.get(key)!=count:
            raise ValueError("PHASE25C_AGGREGATE_METRICS_INCONSISTENT_"+key)
    if counts["unique_ids_with_one_or_more_alerts"]+counts[
        "ids_without_these_three_alerts_NOT_certified_clean"]!=len(br):
        raise ValueError("RESEARCH_ALERT_UNION_COUNT_INCONSISTENT")
    if sum(counts["priority_"+p] for p in (
        "P1_MULTI_ALERT","P2_FACTOR_CHANGE","P3_EXTREME_ADJ_RETURN_ONLY"))!=len(queue):
        raise ValueError("PRIORITY_BUCKET_SUM_MISMATCH")
    order={"P1_MULTI_ALERT":0,"P2_FACTOR_CHANGE":1,
           "P3_EXTREME_ADJ_RETURN_ONLY":2}
    queue.sort(key=lambda q:(
        order[q["priority"]],
        -(q["intra_month_factor_5pct_months"]+
          q["factor_5pct_month_boundary_events"]+
          q["extreme_adj_month_boundary_moves"]),
        str(q["ticker"]),str(q["SimFinId"])
    ))
    report={
        "schema":SCHEMA,
        "status":"UNIQUE_SOURCE_FACTOR_AND_RETURN_ALERT_WORKLIST_RESEARCH_ONLY_NOT_CANONICAL",
        "period":WINDOW,
        "source_price_SHA256":c["source_sha256"],
        "SimFinIds_reviewed":len(br),
        "unique_review_candidates":len(queue),
        "metrics":dict(sorted(counts.items())),
        "priority_method":"P1 multiple alert classes; P2 source Close/Adj.Close factor alert; P3 extreme adj return only. Not a predictive/risk model.",
        "review_guidance":[
            "P1: establish true event date and reason from official exchange/issuer action evidence.",
            "P2: compare SEC/issuer and exchange split/dividend notices with source raw and adjusted closes.",
            "P3: check ticker identity, traded volume, suspensions, delisted return and source anomalies.",
            "A zero alert is never confirmation of correct adjustment; issuer CIK or daily PIT.",
            "A ticker or present-day CIK must never be treated as historical legal issuer proof.",
        ],
        "contains_full_event_dates":False,
        "canonical_backtest_eligible_securities":0,
        "split_events_independently_verified":0,
        "dividend_events_independently_verified":0,
        "delisting_events_independently_verified":0,
        "historical_identity_certified":0,
        "database_modified":False,
        "source_price_modified":False,
        "models_modified":False,
        "network_calls":0,
        "paid_API_calls":0,
        "training_performed":False,
    }
    return report,queue


def _write_report(path:Path, content:str):
    if path.is_symlink():
        raise ValueError("OUTPUT_IS_SYMLINK")
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+".tmp")
    if tmp.is_symlink():
        raise ValueError("OUTPUT_TEMP_SYMLINK")
    tmp.write_text(content,encoding="utf-8")
    tmp.replace(path)


def main()->int:
    root=Path(os.environ.get("LOCALAPPDATA") or str(Path.home()))/(
        "S153ResearchTerminal/runtime")
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--phase25b",type=Path,
                   default=root/"phase25b/simfin_distinct_daily_depth_research.json")
    p.add_argument("--phase25c",type=Path,
                   default=root/"phase25c/simfin_adjustment_factor_source_triage.json")
    p.add_argument("--out",type=Path,
                   default=root/"phase25d/simfin_adjustment_review_worklist.json")
    p.add_argument("--csv",type=Path,
                   default=root/"phase25d/simfin_adjustment_review_worklist.csv")
    a=p.parse_args()
    try:
        inputs={a.phase25b.resolve(),a.phase25c.resolve()}
        outputs={a.out.resolve(),a.csv.resolve()}
        if len(outputs)!=2 or (inputs & outputs) or a.out.is_symlink() or a.csv.is_symlink():
            raise ValueError("UNSAFE_OUTPUT_PATH")
        report,queue=analyze(a.phase25b,a.phase25c)
        # Reports contain candidate metadata only, not priced bars or SEC documents.
        text=json.dumps({**report,"review_queue":queue},ensure_ascii=False,indent=2)+"\n"
        _write_report(a.out,text)
        import io
        buf=io.StringIO(newline="")
        writer=csv.DictWriter(buf,fieldnames=COLS,lineterminator="\n")
        writer.writeheader()
        for row in queue:
            writer.writerow({k:_safe_cell(row[k]) for k in COLS})
        _write_report(a.csv,buf.getvalue())
    except (ValueError,TypeError,KeyError,OSError,UnicodeError):
        print("PHASE25D_BLOCKED: SOURCE_AUDIT_MISMATCH_OR_OUTPUT_UNSAFE")
        return 2
    print(json.dumps({
        "status":report["status"],
        "SimFinIds_reviewed":report["SimFinIds_reviewed"],
        "unique_candidate_ids_requiring_research":report["unique_review_candidates"],
        "multiple_alert_classes":report["metrics"].get(
            "unique_ids_with_multiple_alert_classes",0),
        "source_factor_alert_union":report["metrics"].get(
            "unique_ids_with_source_factor_alert",0),
        "only_extreme_adjusted_moves":report["metrics"].get(
            "extreme_adjusted_move_only_ids",0),
        "quiet_with_no_these_alerts_NOT_certified_clean":report["metrics"].get(
            "ids_without_these_three_alerts_NOT_certified_clean",0),
        "P1_multi_alert":report["metrics"].get("priority_P1_MULTI_ALERT",0),
        "P2_factor_change":report["metrics"].get("priority_P2_FACTOR_CHANGE",0),
        "P3_extreme_only":report["metrics"].get("priority_P3_EXTREME_ADJ_RETURN_ONLY",0),
        "canonical_backtest_eligible_securities":0,
        "private_json":str(a.out),
        "private_csv":str(a.csv),
        "database_modified":False,
    },ensure_ascii=False,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
