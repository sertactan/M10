"""Phase25j: SEC issuer evidence for P1 and full 127-other-candidate source triage.

Reads only existing private Phase24/25d/25e outputs; no SEC API calls or
licensed source redistribution. Filing URL is issuer-CIK document evidence,
NOT historical SimFinId/security identifier/share-class daily PIT proof.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import io
import json
import os
from pathlib import Path

SCHEMA="MERIDYEN_PHASE25J_P1_SEC_FILINGS_127_TRIAGE_V1"
OFFICIAL_DOCS={
 "DOYU":{"CIK":"0001762417","issuer":"DouYu International Holdings Limited",
         "form":"20-F","url":"https://www.sec.gov/Archives/edgar/data/1762417/000141057825000965/doyu-20241231x20f.htm",
         "note":"ADR/ADS class and sponsor ratio remain unverified over full interval"},
 "HUYA":{"CIK":"0001728190","issuer":"HUYA Inc.",
         "form":"20-F","url":"https://www.sec.gov/Archives/edgar/data/1728190/000141057825000781/0001410578-25-000781-index.htm",
         "note":"SEC 20-F accepted 2025-04-17; ADS history and exchange timeline separately required"},
 "IRS":{"CIK":"0000933267","issuer":"IRSA Inversiones y Representaciones Sociedad Anonima",
        "form":"20-F","url":"https://www.sec.gov/Archives/edgar/data/933267/000165495425012190/irsa_20f.htm",
        "note":"GDS underlying class and 2024-11 separate stock distribution need PIT verification"},
 "SITC":{"CIK":"0000894315","issuer":"SITE Centers Corp.",
         "form":"10-K","url":"https://www.sec.gov/Archives/edgar/data/894315/000095017025029989/sitc-20241231.htm",
         "note":"SEC 2024 10-K reports 1-for-4 reverse split AND 2024-10-01 CURB spinoff: two CURB per one SITC. Cannot certify total returns without both"},
 "TDG":{"CIK":"0001260221","issuer":"TransDigm Group Incorporated",
        "form":"10-K","url":"https://www.sec.gov/Archives/edgar/data/1260221/000126022124000083/tdg-20240930.htm",
        "note":"Cash distribution verified elsewhere; class-level history still unverified"},
 "ZIM":{"CIK":"0001654126","issuer":"ZIM Integrated Shipping Services Ltd.",
        "form":"20-F","url":"https://www.sec.gov/Archives/edgar/data/1654126/0001178913-25-000793-index.htm",
        "note":"SEC 2025-03-12 20-F: issuer/CIK only, no independent delisted total return or pricing unit certification"},
}
P1={"P1_MULTI_ALERT"}
OTHERS={"P2_FACTOR_CHANGE","P3_EXTREME_ADJ_RETURN_ONLY"}


def _load(path,name):
    if path.is_symlink() or not path.is_file():
        raise ValueError(name+"_LOCAL_REPORT_MISSING")
    o=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(o,dict):
        raise ValueError(name+"_NOT_JSON")
    return o


def build(phase24,phase25d,phase25e):
    a=_load(phase24,"PHASE24")
    d=_load(phase25d,"PHASE25D")
    e=_load(phase25e,"PHASE25E")
    if (
        a.get("status")!="SIMFIN_ID_TO_CIK_CANDIDATES_ONLY_ZERO_HISTORICAL_ID_CERTIFICATIONS"
        or a.get("historical_identity_certifications")!=0
        or a.get("canonical_price_selections_written")!=0
        or a.get("model_training_performed") is not False
        or d.get("status")!="UNIQUE_SOURCE_FACTOR_AND_RETURN_ALERT_WORKLIST_RESEARCH_ONLY_NOT_CANONICAL"
        or d.get("unique_review_candidates")!=133
        or d.get("canonical_backtest_eligible_securities")!=0
        or d.get("database_modified") is not False
        or e.get("status")!="DATED_SOURCE_PRICE_ANOMALIES_RESEARCH_ONLY_NOT_CANONICAL"
        or e.get("candidate_SimFinIds")!=133
        or e.get("canonical_backtest_eligible_securities")!=0
        or e.get("database_modified") is not False
        or e.get("models_modified") is not False
        or e.get("network_requests")!=0
        or e.get("paid_API_requests")!=0
        or e.get("model_training_performed") is not False
    ):
        raise ValueError("SOURCE_RESEARCH_ONLY_PROVENANCE_MISMATCH")
    records=a.get("candidate_records")
    queue=d.get("review_queue")
    events=e.get("source_only_event_observations")
    per=e.get("per_candidate")
    if not all(isinstance(x,list) for x in (records,queue,events,per)):
        raise ValueError("REQUIRED_PRIOR_ARRAYS_MISSING")
    if len(queue)!=133 or len(per)!=133 or len(events)!=182:
        raise ValueError("REAL_133_182_COHORT_CHANGED")
    refs={}
    for item in records:
        sid=str(item.get("SimFinId","")).strip()
        if not sid or sid in refs:
            raise ValueError("SIMFIN_ID_DUPLICATED")
        refs[sid]=item
    bysid={}
    for item in queue:
        sid=str(item.get("SimFinId","")).strip()
        if not sid or sid in bysid:
            raise ValueError("WORKLIST_ID_DUPLICATED")
        src=refs.get(sid)
        if (not src or item.get("ticker") not in src.get("ticker_strings",[])
            or item.get("present_day_CIK_candidate_NOT_verified")
              not in src.get("candidate_CIKs_NOT_verified",[])
            or item.get("research_only_NOT_PIT") is not True):
            raise ValueError("SIMFINID_CURRENT_CIK_IDENTITY_MISMATCH")
        bysid[sid]=item
    if {str(x.get("SimFinId")) for x in per} != set(bysid):
        raise ValueError("PHASE25E_CANDIDATE_SET_MISMATCH")
    by_priority=Counter(x["priority"] for x in queue)
    if by_priority!={"P1_MULTI_ALERT":6,"P2_FACTOR_CHANGE":88,
                     "P3_EXTREME_ADJ_RETURN_ONLY":39}:
        raise ValueError("PRIORITY_BUCKETS_CHANGED")
    # SEC filing evidence validates the named issuer with that CIK. It
    # does not resolve historical class-level ticker/SimFinId crosswalk.
    p1=[]
    for row in sorted(queue,key=lambda x:x["ticker"]):
        if row["priority"] not in P1:continue
        name=row["ticker"]
        doc=OFFICIAL_DOCS.get(name)
        if not doc or row["present_day_CIK_candidate_NOT_verified"]!=doc["CIK"]:
            raise ValueError("P1_SEC_ISSUER_DOCUMENT_CIK_CONFLICT")
        p1.append({
            "SimFinId":row["SimFinId"],"ticker":name,
            "present_day_CIK_candidate":doc["CIK"],
            "SEC_filing_issuer":doc["issuer"],"SEC_filing_form":doc["form"],
            "SEC_filing_url":doc["url"],
            "SEC_document_identifies_issuer_and_CIK":True,
            "filing_document_evidence_limit":doc["note"],
            "historical_SimFinId_to_CIK_certified":False,
            "historic_ticker_exchange_shareclass_certified":False,
            "effective_daily_PIT_security_identity_certified":False,
            "independent_price_adjustments_certified":False,
        })
    if len(p1)!=6 or set(x["ticker"] for x in p1)!=set(OFFICIAL_DOCS):
        raise ValueError("P1_DOCUMENT_SET_CHANGED")
    other=[]
    event_counts=Counter()
    count_byid=Counter()
    for ev in events:
        sid=str(ev.get("SimFinId","")).strip()
        item=bysid.get(sid)
        if not item or ev.get("ticker")!=item["ticker"] or ev.get("priority")!=item["priority"]:
            raise ValueError("SOURCE_EVENT_SIMFIN_ID_MISMATCH")
        if ev.get("split_or_dividend_proven") is not False or ev.get("historical_CIK_certified") is not False:
            raise ValueError("INCORRECT_CANONICAL_PROMOTION")
        if not isinstance(ev.get("observations"),list) or len(ev["observations"])!=2:
            raise ValueError("EVENT_PRICE_PROVENANCE_MISSING")
        count_byid[sid]+=1
        event_counts[item["priority"]]+=1
        if item["priority"] in P1:continue
        a0,a1=ev["observations"]
        other.append({
            "SimFinId":sid,"ticker":item["ticker"],
            "priority":item["priority"],
            "present_day_CIK_candidate_NOT_verified":
                item["present_day_CIK_candidate_NOT_verified"],
            "source_event_type":ev["kind"],
            "source_observation_date_1":a0["source_date"],
            "source_observation_date_2":a1["source_date"],
            "source_raw_close_1":a0["raw_close"],
            "source_adj_close_1":a0["source_adj_close"],
            "source_raw_close_2":a1["raw_close"],
            "source_adj_close_2":a1["source_adj_close"],
            "official_event_type":"NOT_VERIFIED",
            "official_event_date":"NOT_VERIFIED",
            "official_evidence_url":"",
            "delisting_corporate_action_verified":False,
            "historic_security_identity_verified":False,
            "canonical_adjusted_prices_verified":False,
        })
    if (len(other)!=167 or len({x["SimFinId"] for x in other})!=127
        or event_counts!={"P1_MULTI_ALERT":15,"P2_FACTOR_CHANGE":127,
                            "P3_EXTREME_ADJ_RETURN_ONLY":40}):
        raise ValueError("OTHER_127_EVENT_COUNTS_CHANGED")
    for record in per:
        sid=str(record.get("SimFinId"))
        if count_byid[sid]!=record.get("dated_source_event_count"):
            raise ValueError("PER_SECURITY_SOURCE_EVENT_DEPTH_MISMATCH")
    other.sort(key=lambda r:(r["priority"],r["ticker"],r["SimFinId"],
                             r["source_observation_date_1"],r["source_event_type"]))
    return {
        "schema":SCHEMA,
        "status":"SEC_FILING_ISSUER_LINKS_REVIEWED_127_CANDIDATES_EVENT_TRIAGED_NOT_HISTORICAL_PIT",
        "p1_count":len(p1),
        "official_SEC_issuer_CIK_document_refs":len(p1),
        "p1_document_refs":p1,
        "other_research_candidates":127,
        "other_source_price_event_rows":len(other),
        "events_by_priority":dict(event_counts),
        "other_event_review_queue":other,
        "warnings":[
          "SEC issuer-CIK evidence is not independent verification that a SimFinId maps to the same share class on every historical day.",
          "SITC 2024 reverse split and CURB spinoff add noncash share actions not covered by cash-only factor matching.",
          "Every 21/21-month surviving ticker cohort is survivorship-selected; do not backtest the entire US market from this cohort alone.",
          "P2/P3 source events have NO verified official corporate action or historical issuer identity; flags are not a complete actions universe.",
        ],
        "fully_verified_historical_SimFinId_CIK_pairs":0,
        "certified_p2p3_split_dividend_adjustments":0,
        "certified_delisting_terminal_returns":0,
        "canonical_backtest_eligible_securities":0,
        "WF9_allowed":False,"Learning_V3_allowed":False,
        "source_files_modified":False,"production_DB_modified":False,
        "models_modified":False,"network_requests":0,
    }


def _safe_cell(x):
    s=str(x)
    return "'"+s if s.lstrip().startswith(("=","+","-","@","\t","\r")) else s


def main():
    root=Path(os.environ.get("LOCALAPPDATA") or str(Path.home()))/"S153ResearchTerminal/runtime"
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase24",type=Path,default=root/"phase24/simfin_sec_cik_candidates.json")
    parser.add_argument("--phase25d",type=Path,default=root/"phase25d/simfin_adjustment_review_worklist.json")
    parser.add_argument("--phase25e",type=Path,default=root/"phase25e/simfin_dated_source_anomaly_packets.json")
    parser.add_argument("--out",type=Path,default=root/"phase25j/sec_p1_cik_and_p2p3_event_triage.json")
    parser.add_argument("--csv",type=Path,default=root/"phase25j/p2p3_127_source_event_queue.csv")
    a=parser.parse_args()
    try:
        output_paths={a.out.resolve(),a.csv.resolve()}
        if (len(output_paths)!=2 or output_paths.intersection(
                {x.resolve() for x in (a.phase24,a.phase25d,a.phase25e)})
            or a.out.is_symlink() or a.csv.is_symlink()):
            raise ValueError("OUTPUT_MAY_NOT_OVERWRITE_PRIVATE_SOURCE")
        report=build(a.phase24,a.phase25d,a.phase25e)
        a.out.parent.mkdir(parents=True,exist_ok=True)
        temp=a.out.with_name(a.out.name+".tmp")
        if temp.is_symlink():raise ValueError("TEMP_OUTPUT_SYMLINK")
        temp.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
        temp.replace(a.out)
        buf=io.StringIO(newline="")
        cols=list(report["other_event_review_queue"][0])
        writer=csv.DictWriter(buf,fieldnames=cols,lineterminator="\n")
        writer.writeheader()
        for row in report["other_event_review_queue"]:
            writer.writerow({k:_safe_cell(row[k]) for k in cols})
        t=a.csv.with_name(a.csv.name+".tmp")
        if t.is_symlink():raise ValueError("CSV_OUTPUT_TEMP_SYMLINK")
        t.write_text(buf.getvalue(),encoding="utf-8")
        t.replace(a.csv)
    except (ValueError,KeyError,TypeError,OSError):
        print("PHASE25J_BLOCKED: PRIVATE_PRIOR_REPORT_IDENTITY_OR_COHORT_INVALID")
        return 2
    print(json.dumps({
       "status":report["status"],"p1_SEC_issuer_CIK_document_refs":6,
       "p1_full_historical_SimFinId_CIK_certified":0,
       "other_distinct_SimFinIds":report["other_research_candidates"],
       "other_source_event_rows":report["other_source_price_event_rows"],
       "total_P1_P2_P3_source_events":182,
       "canonical_eligible":0,
       "report_json":str(a.out),"other_queue_csv":str(a.csv),
       "production_DB_modified":False
    },ensure_ascii=False,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
