"""Phase25k: fail-closed acceptance ledger for historical PIT/backtest/Learning V3.

Combines observed read-only Windows market DB gate and the complete 133
research candidate source triage. Never writes canonical SQLite or trains.
"""
from __future__ import annotations
import argparse,csv,io,json,os
from pathlib import Path
from collections import Counter

SCHEMA="MERIDYEN_PHASE25K_FULL_UNIVERSE_CANONICAL_ACCEPTANCE_LEDGER_V1"
REQUIRED_EVIDENCE=(
    "historical_cik_shareclass_interval",
    "daily_identity_exchange_timezone",
    "issuer_corporate_action_full_interval",
    "source_adjustment_method_verified",
    "delisting_terminal_return_verified",
    "SEC_published_available_at",
    "authoritative_daily_prices",
    "canonical_month_membership",
    "mature_252_session_outcome_labels",
)
SEC_P1={"DOYU","HUYA","IRS","SITC","TDG","ZIM"}

def load(path,name):
    if path.is_symlink() or not path.is_file():
        raise ValueError(name+"_REPORT_MISSING")
    d=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(d,dict):
        raise ValueError(name+"_BAD_REPORT")
    return d

def reconcile(p25i:Path,p25j:Path):
    i=load(p25i,"PHASE25I")
    j=load(p25j,"PHASE25J")
    if (i.get("schema")!="MERIDYEN_PHASE25I_REAL_MARKET_PIT_TRAINING_GATE_V1"
        or i.get("status")!="FULL_CHAIN_REAL_DATA_BLOCKED_NOT_TRAINED"
        or i.get("pit_backtest_eligible") is not False
        or i.get("walk_forward_executed") is not False
        or i.get("Learning_V3_executed") is not False
        or i.get("source_db_modified") is not False
        or j.get("schema")!="MERIDYEN_PHASE25J_P1_SEC_FILINGS_127_TRIAGE_V1"
        or j.get("p1_count")!=6
        or j.get("other_research_candidates")!=127
        or j.get("other_source_price_event_rows")!=167
        or j.get("fully_verified_historical_SimFinId_CIK_pairs")!=0
        or j.get("canonical_backtest_eligible_securities")!=0
        or j.get("production_DB_modified") is not False
        or j.get("WF9_allowed") is not False
        or j.get("Learning_V3_allowed") is not False):
        raise ValueError("REAL_RESEARCH_INPUTS_NOT_FAIL_CLOSED")
    byid={}
    p1=j.get("p1_document_refs")
    other=j.get("other_event_review_queue")
    if not isinstance(p1,list) or len(p1)!=6 or not isinstance(other,list) or len(other)!=167:
        raise ValueError("RESEARCH_ID_AND_EVENT_COUNT_MISMATCH")
    for x in p1:
        sid=str(x["SimFinId"])
        if x.get("ticker") not in SEC_P1 or sid in byid or x.get("historical_SimFinId_to_CIK_certified") is not False:
            raise ValueError("UNSAFE_P1_IDENTITY")
        byid[sid]={"SimFinId":sid,"ticker":x["ticker"],
                   "priority":"P1_MULTI_ALERT","current_CIK_candidate":x["present_day_CIK_candidate"],
                   "source_event_count":0,"SEC_issuer_document_URL":x["SEC_filing_url"]}
    for x in other:
        sid=str(x["SimFinId"])
        if sid not in byid:
            byid[sid]={"SimFinId":sid,"ticker":x["ticker"],"priority":x["priority"],
                       "current_CIK_candidate":x["present_day_CIK_candidate_NOT_verified"],
                       "source_event_count":0,"SEC_issuer_document_URL":""}
        rec=byid[sid]
        if (rec["ticker"]!=x["ticker"] or rec["priority"]!=x["priority"]
            or rec["current_CIK_candidate"]!=x["present_day_CIK_candidate_NOT_verified"]
            or x["canonical_adjusted_prices_verified"] is not False
            or x["historic_security_identity_verified"] is not False
            or x["delisting_corporate_action_verified"] is not False):
            raise ValueError("UNSAFE_RESEARCH_EVENT")
        rec["source_event_count"]+=1
    if len(byid)!=133 or sum(1 for r in byid.values() if r["priority"]=="P1_MULTI_ALERT")!=6:
        raise ValueError("SECURITY_COHORT_MISMATCH")
    # Include P1 source-event count from earlier research (15); P1 detail
    # events are not in phase25j other_event_review_queue by design.
    for r in byid.values():
        if r["priority"]=="P1_MULTI_ALERT":
            r["source_event_count"]=None
    counts=i.get("counts") or {}
    if (counts.get("membership",[None])[0]!=0
        or counts.get("canonical_backtest_price",[None])[0]!=0
        or counts.get("corporate_actions",[None])[0]!=0
        or counts.get("complete_WF5",[None])[0]!=0
        or counts.get("complete_WF6",[None])[0]!=0):
        raise ValueError("PHASE25I_DATABASE_CHANGED_REAUDIT_REQUIRED")
    ledger=[]
    for sid,r in sorted(byid.items(),key=lambda pair:(pair[1]["priority"],pair[1]["ticker"],pair[0])):
        note=("SITC 2024 reverse split and CURB spinoff both require sourced share/price basis reconciliation"
              if r["ticker"]=="SITC" else
              "IRS separate cash and 3.6013447 percent stock distribution; GDS class"
              if r["ticker"]=="IRS" else
              "Source-only anomaly, not a validated corporate action")
        ledger.append({**r,
            "missing_evidence":"|".join(REQUIRED_EVIDENCE),
            "special_instrument_or_action_note":note,
            "canonical_approved":False,
            "actual_wf9_allowed":False,
            "learning_v3_allowed":False})
    return {"schema":SCHEMA,"status":"CANONICAL_RESEARCH_LEDGER_CREATED_ALL_SECURITY_ACCEPTANCE_BLOCKED",
        "period":{"start":"2024-01-01","end":"2025-09-30"},
        "research_candidate_ids":len(ledger),"evidence_required":list(REQUIRED_EVIDENCE),
        "blockers_from_real_SQLite":i["blockers"],
        "research_priorities":dict(Counter(r["priority"] for r in ledger)),
        "accepted_canonical_securities":0,"survivorship_bias_check_passed":False,
        "price_split_dividend_fully_verified":False,
        "historical_CIK_daily_identity_verified":False,
        "delisting_total_returns_verified":False,
        "actual_WF9_executed":False,"actual_Learning_V3_executed":False,
        "Learning_V3_model_promotion_allowed":False,
        "production_DB_modified":False,"SEC_financials_modified":False,
        "licensed_price_data_modified":False,"network_requests":0,
        "ledger":ledger}

def main():
    root=Path(os.environ.get("LOCALAPPDATA") or str(Path.home()))/"S153ResearchTerminal/runtime"
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--phase25i",type=Path,default=root/"phase25i/real_market_gate_matrix_2024_2025.json")
    p.add_argument("--phase25j",type=Path,default=root/"phase25j/sec_p1_cik_and_p2p3_event_triage.json")
    p.add_argument("--out",type=Path,default=root/"phase25k/canonical_acceptance_133_research_ledger.json")
    p.add_argument("--csv",type=Path,default=root/"phase25k/canonical_acceptance_133_research_ledger.csv")
    a=p.parse_args()
    try:
        sources={a.phase25i.resolve(),a.phase25j.resolve()}
        if (a.out.resolve() in sources or a.csv.resolve() in sources
            or a.out.resolve()==a.csv.resolve()
            or a.out.is_symlink() or a.csv.is_symlink()):
            raise ValueError("UNSAFE_OUTPUT")
        rep=reconcile(a.phase25i,a.phase25j)
        data=json.dumps(rep,ensure_ascii=False,indent=2)+"\n"
        b=io.StringIO(newline="")
        cols=list(rep["ledger"][0])
        w=csv.DictWriter(b,fieldnames=cols,lineterminator="\n")
        w.writeheader()
        for row in rep["ledger"]:
            w.writerow({k:str(v) if v is not None else "" for k,v in row.items()})
        a.out.parent.mkdir(parents=True,exist_ok=True)
        a.csv.parent.mkdir(parents=True,exist_ok=True)
        for path,body in [(a.out,data),(a.csv,b.getvalue())]:
            tmp=path.with_name(path.name+".tmp")
            if tmp.is_symlink():raise ValueError("TEMP_OUTPUT_SYMLINK")
            tmp.write_text(body,encoding="utf-8")
            tmp.replace(path)
    except (OSError,ValueError,TypeError,KeyError):
        print("PHASE25K_BLOCKED: INPUT_NOT_SAFE_OR_COHORT_MISMATCH")
        return 2
    print(json.dumps({
        "status":rep["status"],"candidate_ids":rep["research_candidate_ids"],
        "priority_counts":rep["research_priorities"],
        "canonical_accepted":0,
        "WF9_executed":False,"Learning_V3_executed":False,
        "out_json":str(a.out),"out_csv":str(a.csv)
    },ensure_ascii=False,indent=2))
    return 0
if __name__=="__main__":
    raise SystemExit(main())
