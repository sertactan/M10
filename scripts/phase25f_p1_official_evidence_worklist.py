"""Phase25f — research-only official-evidence review queue for dated SimFin P1.

Turns Phase25e's source price observations into operator-reviewable rows.
It does NOT query SEC/exchanges, assert a corporate action, or certify PIT.
The manual evidence fields remain blank until externally corroborated.
Only writes private new Phase25f JSON/CSV; no database or input modification.
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
import hashlib
import io
import json
import math
import os
from pathlib import Path

from scripts.phase25e_simfin_dated_source_anomalies import SCHEMA as E_SCHEMA
from scripts.phase25b_simfin_distinct_daily_depth_audit import WINDOW

SCHEMA = "MERIDYEN_PHASE25F_P1_OFFICIAL_SOURCE_EVIDENCE_WORKLIST_V1"
STATUS = "DATED_SOURCE_PRICE_ANOMALIES_RESEARCH_ONLY_NOT_CANONICAL"
EVENT_TYPES = {
    "SOURCE_FACTOR_WITHIN_MONTH_RANGE_5PCT": "intra_month_ranges",
    "SOURCE_FACTOR_MONTH_BOUNDARY_5PCT": "factor_month_boundaries",
    "SOURCE_ADJ_CLOSE_MONTH_BOUNDARY_MOVE_50PCT": "extreme_adjusted_month_boundaries",
}
PRIORITY = "P1_MULTI_ALERT"

CSV_COLUMNS = [
    "priority", "SimFinId", "ticker", "present_day_CIK_candidate_NOT_verified",
    "source_event_kind", "source_months", "source_first_date", "source_last_date",
    "source_first_raw_close", "source_first_adj_close",
    "source_last_raw_close", "source_last_adj_close",
    "factor_range_pct_or_change_pct_or_adjusted_move_pct",
    "metric_type", "official_evidence_url_TO_RESEARCH",
    "official_issuer_name_TO_VERIFY", "official_corporate_action_type_TO_VERIFY",
    "official_ex_or_effective_date_TO_VERIFY", "official_publication_time_TO_VERIFY",
    "historical_issuer_CIK_TO_VERIFY", "review_outcome",
]

def _read_report(path: Path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("PHASE25E_PRIVATE_REPORT_UNAVAILABLE")
    raw = path.read_bytes()
    payload = json.loads(raw)
    if not isinstance(payload,dict):
        raise ValueError("PHASE25E_REPORT_NOT_OBJECT")
    return payload, hashlib.sha256(raw).hexdigest()


def _safe_csv(x):
    t=str(x)
    # Prevent Excel interpretation of untrusted vendor strings as formulas.
    return "'"+t if t.lstrip().startswith(("=","+","-","@","\t","\r")) else t


def _valid_num(x):
    return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) and x>0


def _source_observation(observation):
    if not isinstance(observation,dict):
        raise ValueError("INVALID_SOURCE_PRICE_OBSERVATION")
    d=observation.get("source_date")
    if not isinstance(d,str) or len(d)!=10 or not WINDOW["start"]<=d<=WINDOW["end"]:
        raise ValueError("SOURCE_DATE_OUTSIDE_AUDITED_WINDOW")
    from datetime import date
    try:
        date.fromisoformat(d)
    except ValueError as e:
        raise ValueError("SOURCE_DATE_NOT_VALID") from e
    if (not _valid_num(observation.get("raw_close"))
        or not _valid_num(observation.get("source_adj_close"))
        or not _valid_num(observation.get("source_close_to_adjusted_factor"))):
        raise ValueError("INVALID_SOURCE_PRICE_EVIDENCE_VALUE")
    actual=observation["raw_close"]/observation["source_adj_close"]
    if not math.isclose(actual,observation["source_close_to_adjusted_factor"],rel_tol=1e-9):
        raise ValueError("SOURCE_FACTOR_MISMATCH")
    return d


def build(phase25e: Path, *, priority: str = PRIORITY):
    a, input_sha=_read_report(phase25e)
    if (
        a.get("schema") != E_SCHEMA
        or a.get("status") != STATUS
        or a.get("window") != WINDOW
        or a.get("canonical_backtest_eligible_securities") != 0
        or a.get("historical_identity_certifications") != 0
        or a.get("adjusted_prices_certified") != 0
        or a.get("split_verified") != 0 or a.get("dividend_verified") != 0
        or a.get("database_modified") is not False
        or a.get("source_price_modified") is not False
        or a.get("SEC_records_modified") is not False
        or a.get("models_modified") is not False
        or a.get("model_training_performed") is not False
        or a.get("network_requests") != 0
        or a.get("paid_API_requests") != 0
    ):
        raise ValueError("PHASE25E_NOT_SAFE_RESEARCH_EVIDENCE")
    if priority != PRIORITY:
        raise ValueError("ONLY_P1_OFFICIAL_EVIDENCE_FIRST_SUPPORTED")
    people=a.get("per_candidate")
    source_events=a.get("source_only_event_observations")
    p1=a.get("P1_candidates")
    if not all(isinstance(x,list) for x in (people,source_events,p1)):
        raise ValueError("PHASE25E_REQUIRED_ARRAYS_MISSING")
    if (
        not 0 < len(people) == a.get("candidate_SimFinIds") <= 100000
        or not 0 < len(p1) <= len(people)
    ):
        raise ValueError("PHASE25E_COHORT_INVALID")
    ids={}
    totals=Counter()
    for item in people:
        sid=str(item.get("SimFinId","")).strip()
        if not sid or sid in ids or not item.get("ticker"):
            raise ValueError("PHASE25E_DUPLICATE_OR_MISSING_ID")
        for field in EVENT_TYPES.values():
            v=item.get(field)
            if isinstance(v,bool) or not isinstance(v,int) or not 0<=v<=21:
                raise ValueError("PHASE25E_PER_CANDIDATE_COUNT_INVALID")
        ids[sid]=item
    p1_ids=set()
    for item in p1:
        sid=str(item.get("SimFinId","")).strip()
        if sid in p1_ids or sid not in ids or item != ids[sid] or item.get("priority")!=PRIORITY:
            raise ValueError("PHASE25E_P1_COHORT_PROVENANCE_MISMATCH")
        p1_ids.add(sid)
    if len(p1_ids) != a.get("priority_counts",{}).get(PRIORITY):
        raise ValueError("PHASE25E_P1_COUNT_MISMATCH")

    observed=Counter()
    event_rows=[]
    for ev in source_events:
        sid=str(ev.get("SimFinId","")).strip()
        person=ids.get(sid)
        if person is None or ev.get("ticker")!=person["ticker"] or ev.get("priority")!=person["priority"]:
            raise ValueError("PHASE25E_SOURCE_EVENT_UNRECONCILED")
        kind=ev.get("kind")
        if kind not in EVENT_TYPES or ev.get("split_or_dividend_proven") is not False or ev.get("historical_CIK_certified") is not False:
            raise ValueError("EVENT_KIND_OR_CERTIFICATION_UNSAFE")
        obs=ev.get("observations")
        if not isinstance(obs,list) or len(obs)!=2:
            raise ValueError("SOURCE_EVENT_MISSING_TWO_PRICE_OBSERVATIONS")
        d0,d1=(_source_observation(o) for o in obs)
        # Within-month min/max points needn't be returned in date order.
        # Preserve the exact source position and make dates explicit.
        month=ev.get("month")
        months=ev.get("months")
        if kind=="SOURCE_FACTOR_WITHIN_MONTH_RANGE_5PCT":
            if not isinstance(month,str) or d0[:7]!=month or d1[:7]!=month:
                raise ValueError("INTRA_MONTH_EVENT_DATE_MISMATCH")
            metric=ev.get("factor_range_pct")
            metric_type="SOURCE_FACTOR_MONTH_RANGE_PCT"
            label=month
        else:
            if not isinstance(months,list) or len(months)!=2 or d0[:7]!=months[0] or d1[:7]!=months[1]:
                raise ValueError("MONTH_BOUNDARY_EVENT_DATE_MISMATCH")
            label="|".join(months)
            if kind=="SOURCE_FACTOR_MONTH_BOUNDARY_5PCT":
                metric=ev.get("absolute_factor_ratio_change_pct")
                metric_type="SOURCE_FACTOR_MONTH_BOUNDARY_CHANGE_PCT"
            else:
                metric=ev.get("signed_source_adj_close_move_pct")
                metric_type="SOURCE_ADJ_CLOSE_MONTH_BOUNDARY_RETURN_PCT"
        if (isinstance(metric,bool) or not isinstance(metric,(int,float))
            or not math.isfinite(metric)
            or abs(metric)<(50 if kind=="SOURCE_ADJ_CLOSE_MONTH_BOUNDARY_MOVE_50PCT" else 5)):
            raise ValueError("EVENT_SOURCE_METRIC_OUT_OF_RANGE")
        observed[(sid,EVENT_TYPES[kind])]+=1
        totals[kind]+=1
        if sid not in p1_ids:
            continue
        event_rows.append({
            "priority":PRIORITY,
            "SimFinId":sid,
            "ticker":person["ticker"],
            "present_day_CIK_candidate_NOT_verified":
                ev.get("present_day_CIK_candidate_NOT_verified",""),
            "source_event_kind":kind,
            "source_months":label,
            "source_first_date":d0,
            "source_last_date":d1,
            "source_first_raw_close":obs[0]["raw_close"],
            "source_first_adj_close":obs[0]["source_adj_close"],
            "source_last_raw_close":obs[1]["raw_close"],
            "source_last_adj_close":obs[1]["source_adj_close"],
            "factor_range_pct_or_change_pct_or_adjusted_move_pct":metric,
            "metric_type":metric_type,
            "official_evidence_url_TO_RESEARCH":"",
            "official_issuer_name_TO_VERIFY":"",
            "official_corporate_action_type_TO_VERIFY":"",
            "official_ex_or_effective_date_TO_VERIFY":"",
            "official_publication_time_TO_VERIFY":"",
            "historical_issuer_CIK_TO_VERIFY":"",
            "review_outcome":"UNREVIEWED_NO_INDEPENDENT_EVIDENCE",
        })
    for sid,item in ids.items():
        for field in EVENT_TYPES.values():
            if observed[(sid,field)]!=item[field]:
                raise ValueError("PHASE25E_PER_CANDIDATE_EVENTS_NOT_RECONCILED")
    if sum(totals.values())!=len(source_events):
        raise ValueError("PHASE25E_TOTAL_EVENTS_NOT_RECONCILED")
    for kind,count in totals.items():
        if a.get("event_counts",{}).get(kind)!=count:
            raise ValueError("PHASE25E_EVENT_TOTALS_MISMATCH")
    event_rows.sort(key=lambda r:(r["ticker"],r["SimFinId"],
                                  min(r["source_first_date"],r["source_last_date"]),
                                  r["source_event_kind"]))
    by_ticker=defaultdict(lambda:{"source_events":0,"first_source_date":None,
                                   "last_source_date":None})
    for event in event_rows:
        t=event["ticker"]
        w=by_ticker[t]
        w["source_events"]+=1
        for d in [event["source_first_date"],event["source_last_date"]]:
            w["first_source_date"]=min(w["first_source_date"] or d,d)
            w["last_source_date"]=max(w["last_source_date"] or d,d)
    result={
        "schema":SCHEMA,
        "status":"P1_INDEPENDENT_CORPORATE_ACTION_EVIDENCE_REVIEW_NEEDED_NOT_CERTIFIED",
        "input_phase25e_sha256":input_sha,
        "source_price_SHA256":a.get("source_SHA256"),
        "window":WINDOW,
        "P1_SimFinIds":len(p1_ids),
        "P1_dated_source_events":len(event_rows),
        "P1_ticker_event_date_ranges":dict(sorted(by_ticker.items())),
        "source_25e_all_candidate_events":dict(sorted(totals.items())),
        "review_rows":event_rows,
        "separate_independent_evidence_obtained":False,
        "official_exchange_or_issuer_corporate_action_verified":0,
        "historical_issuer_CIK_verified":0,
        "split_verified":0,"dividend_verified":0,
        "adjusted_price_validated":0,"delisting_proceeds_verified":0,
        "canonical_backtest_eligible_securities":0,
        "original_sources_modified":False,
        "operational_DB_modified":False,"models_modified":False,
        "network_requests":0,"paid_API_requests":0,
        "model_training_performed":False,
    }
    return result


def _write(path:Path,data:str):
    if path.is_symlink() or path.with_name(path.name+".tmp").is_symlink():
        raise ValueError("UNSAFE_OUTPUT_SYMLINK")
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+".tmp")
    temp.write_text(data,encoding="utf-8")
    temp.replace(path)


def main():
    root=Path(os.environ.get("LOCALAPPDATA") or str(Path.home()))/"S153ResearchTerminal/runtime"
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--phase25e",type=Path,
                   default=root/"phase25e/simfin_dated_source_anomaly_packets.json")
    p.add_argument("--out",type=Path,
                   default=root/"phase25f/p1_independent_source_review_queue.json")
    p.add_argument("--csv",type=Path,
                   default=root/"phase25f/p1_independent_source_review_queue.csv")
    a=p.parse_args()
    try:
        outputs={a.out.resolve(),a.csv.resolve()}
        if len(outputs)!=2 or a.phase25e.resolve() in outputs:
            raise ValueError("REVIEW_OUTPUT_OVERWRITES_INPUT")
        result=build(a.phase25e)
        csvfile=io.StringIO(newline="")
        writer=csv.DictWriter(csvfile,fieldnames=CSV_COLUMNS,lineterminator="\n")
        writer.writeheader()
        for row in result["review_rows"]:
            writer.writerow({field:_safe_csv(row[field]) for field in CSV_COLUMNS})
        _write(a.out,json.dumps(result,ensure_ascii=False,indent=2)+"\n")
        _write(a.csv,csvfile.getvalue())
    except (OSError,ValueError,KeyError,TypeError,UnicodeError):
        print("PHASE25F_BLOCKED: PHASE25E_REPORT_OR_EVENT_PROVENANCE_INVALID")
        return 2
    print(json.dumps({
        "status":result["status"],
        "P1_SimFinIds":result["P1_SimFinIds"],
        "P1_dated_source_events":result["P1_dated_source_events"],
        "P1_ticker_event_date_ranges":result["P1_ticker_event_date_ranges"],
        "independent_corporate_actions_verified":0,
        "historical_CIK_verified":0,
        "canonical_backtest_eligible_securities":0,
        "report_json":str(a.out),"review_csv":str(a.csv),
        "operational_DB_modified":False
    },ensure_ascii=False,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
