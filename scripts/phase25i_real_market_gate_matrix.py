"""Phase25i: real Windows 2024-2025 full-chain fail-closed PIT readiness matrix.

Only read-only SQLite (immutable input path) and existing private Phase24,
Phase25b and Phase25h evidence reports. Does not bootstrap, write into the
operational DB, change models, invent delisted return or start a synthetic
Learning V3 run. Explicit zero selections block WF9 and Learning V3.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
from datetime import date
import json
import os
from pathlib import Path
import sqlite3

SCHEMA = "MERIDYEN_PHASE25I_REAL_MARKET_PIT_TRAINING_GATE_V1"
START,END = "2024-01-01","2025-09-30"
C_STATUS = "15_PRIMARY_REFERENCE_COMPARISONS_RESEARCH_ONLY_PRICE_AND_PIT_NOT_CERTIFIED"
P24_STATUS = "SIMFIN_ID_TO_CIK_CANDIDATES_ONLY_ZERO_HISTORICAL_ID_CERTIFICATIONS"
P25B_STATUS = "DISTINCT_SIMFINID_DATE_COUNTS_VERIFIED_RESEARCH_ONLY_NOT_PIT"
NAMES={
    "universe_snapshot_membership","canonical_price_selection","corporate_actions",
    "security_master","wf5_replay_runs","wf6_walk_forward_runs",
    "fundamental_facts_source","canonical_model_features",
}


def _load(path, label):
    if path.is_symlink() or not path.is_file():
        raise ValueError(label+"_SOURCE_MISSING")
    o=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(o,dict):
        raise ValueError(label+"_INVALID_JSON")
    return o


def _sql(con,query,args=()):
    return con.execute(query,args).fetchall()


def assess(db:Path,report24:Path,report25b:Path,report25h:Path,parquet:Path):
    p24=_load(report24,"PHASE24")
    p25b=_load(report25b,"PHASE25B")
    p25h=_load(report25h,"PHASE25H")
    if (
        p24.get("status")!=P24_STATUS or p24.get("historical_identity_certifications")!=0
        or p24.get("ticker_only_identity_link_accepted") is not False
        or p24.get("canonical_price_selections_written")!=0
        or p24.get("model_training_performed") is not False
        or p25b.get("status")!=P25B_STATUS
        or p25b.get("canonical_eligible")!=0
        or p25b.get("historical_SimFinId_CIK_certifications")!=0
        or p25b.get("price_adjustment_certifications")!=0
        or p25b.get("operational_DB_modified") is not False
        or p25b.get("model_training_performed") is not False
        or p25h.get("status")!=C_STATUS
        or p25h.get("source_warning_rows")!=15
        or p25h.get("corporate_action_price_adjustment_certified")!=0
        or p25h.get("historical_issuer_CIK_certified")!=0
        or p25h.get("canonical_backtest_eligible_securities")!=0
        or p25h.get("walk_forward_backtest_allowed") is not False
        or p25h.get("Learning_V3_allowed") is not False
        or p25h.get("production_DB_modified") is not False
        or p25h.get("training_performed") is not False
        or p24.get("period")!={"start":START,"end":END}
        or p25b.get("window")!={"start":START,"end":END}
    ):
        raise ValueError("PRIOR_CANONICAL_PROVENANCE_NOT_RECONCILED")
    if db.is_symlink() or not db.is_file():
        raise ValueError("REAL_OPERATIONAL_DATABASE_MISSING")
    out={"schema":SCHEMA,
        "status":"FULL_CHAIN_REAL_DATA_BLOCKED_NOT_TRAINED",
        "window":{"start":START,"end":END},
        "private_research_input":{
            "simfin_ids_considered":p24.get("simfin_ids_in_window"),
            "qualified_21_month_ids":p25b.get("phase25a_prior_candidate_21months"),
            "p1_source_events_joined_to_references":15,
            "independently_certified_historical_simfin_cik":0,
            "certified_vendor_price_adjustments":0,
            "official_cash_research_references":p25h.get("reference_count_unique_primary_cash_events"),
        },
        "db_sources":{"sqlite_read_only":True,"parquet_root_exists":parquet.is_dir()},
        "counts":{},
        "blockers":[],
        "pit_backtest_eligible":False,"walk_forward_executed":False,
        "Learning_V3_executed":False,"model_promotion_allowed":False,
        "source_db_modified":False,"SEC_data_modified":False,"network_requests":0,
    }
    with closing(sqlite3.connect(db.resolve().as_uri()+"?mode=ro",uri=True,timeout=15)) as con:
        con.execute("PRAGMA query_only=ON")
        tables={r[0] for r in _sql(con,"SELECT name FROM sqlite_master WHERE type='table'")}
        missing=sorted(NAMES-tables)
        if missing:
            out["blockers"].append("REQUIRED_TABLES_MISSING")
            out["missing_tables"]=missing
            return out
        key={
            "membership":"SELECT COUNT(*),COUNT(DISTINCT snapshot_date),COUNT(DISTINCT security_id) FROM universe_snapshot_membership WHERE snapshot_date BETWEEN ? AND ?",
            "canonical_backtest_price":"SELECT COUNT(*),COUNT(DISTINCT security_id) FROM canonical_price_selection WHERE purpose='BACKTEST_ADJUSTED' AND start_date<=? AND end_date>=?",
            "corporate_actions":"SELECT COUNT(*) FROM corporate_actions WHERE ex_date BETWEEN ? AND ? OR effective_date BETWEEN ? AND ?",
            "dated_delisted_security_master":"SELECT COUNT(*) FROM security_master WHERE delisted_date BETWEEN ? AND ?",
            "complete_WF5":"SELECT COUNT(*) FROM wf5_replay_runs WHERE status='COMPLETE'",
            "complete_WF6":"SELECT COUNT(*) FROM wf6_walk_forward_runs WHERE status='COMPLETE'",
        }
        for label,query in key.items():
            if label=="canonical_backtest_price":
                params=(END,START)
            elif label=="corporate_actions":
                params=(START,END,START,END)
            elif label in {"complete_WF5","complete_WF6"}:
                params=()
            else:
                params=(START,END)
            out["counts"][label]=_sql(con,query,params)[0]
        source_rows=_sql(con,
            "SELECT source,COUNT(*) FROM universe_snapshot_membership WHERE snapshot_date BETWEEN ? AND ? GROUP BY source",
            (START,END))
        out["counts"]["membership_by_source"]={str(k):v for k,v in source_rows}
        out["db_sources"]["historical_CIK_identifier_interval_table_present"] = (
            "security_identifier_history" in tables)
        out["db_sources"]["explicit_delisting_event_table_present"] = (
            "delisting_events" in tables)
        out["db_sources"]["mature_learning_labels_table_present"] = (
            "learning_v2_wf5_mature_labels" in tables)
    c=out["counts"]
    if c["membership"][0]==0 or c["membership"][1] < 21:
        out["blockers"].append("NOT_ALL_21_MONTHLY_CANONICAL_MEMBERSHIP_SNAPSHOTS")
    if c["canonical_backtest_price"][1]==0:
        out["blockers"].append("NO_AUTHORITATIVE_ADJUSTED_BACKTEST_PRICE_SELECTION")
    if c["corporate_actions"][0]==0:
        out["blockers"].append("NO_PERSISTED_CORPORATE_ACTION_EVENTS_FOR_WINDOW")
    if not out["db_sources"]["historical_CIK_identifier_interval_table_present"]:
        out["blockers"].append("HISTORICAL_ISSUER_SHARECLASS_CIK_CROSSWALK_NOT_CERTIFIED")
    if not out["db_sources"]["explicit_delisting_event_table_present"]:
        out["blockers"].append("NO_EXPLICIT_DELISTING_EVENT_AND_TERMINAL_RETURNS")
    if c["complete_WF5"][0]==0:
        out["blockers"].append("NO_COMPLETE_WF5_EVIDENCE")
    if c["complete_WF6"][0]==0:
        out["blockers"].append("NO_COMPLETE_WF6_OOS_EVIDENCE")
    if not out["db_sources"]["mature_learning_labels_table_present"]:
        out["blockers"].append("MATURE_VERIFIED_LEARNING_LABELS_NOT_PERSISTED")
    out["blockers"].append("INDEPENDENT_SECURITY_ID_PRICE_ACTION_PUBLICATION_PIT_REQUIRED")
    out["next_actions"]=[
        "Validate 21 monthly membership files and issuer/share-class mapping BEFORE importing canonical PIT snapshots.",
        "Acquire independent historical corporate actions, cash-vs-split vs ADR units and delisting terminal prices; reconcile against SimFin without rewriting source.",
        "Approve complete, adjustment-certified daily price bars and dated security identity before any canonical_price_selection rows.",
        "Run the existing WF9 preflight and only execute walk-forward on a fully verified dataset; Learning V3 requires mature labels and strict OOS dates.",
    ]
    return out


def main():
    runtime=Path(os.environ.get("LOCALAPPDATA") or str(Path.home()))/"S153ResearchTerminal/runtime"
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db",type=Path,default=runtime/"data/runtime/operational.db")
    p.add_argument("--phase24",type=Path,default=runtime/"phase24/simfin_sec_cik_candidates.json")
    p.add_argument("--phase25b",type=Path,default=runtime/"phase25b/simfin_distinct_daily_depth_research.json")
    p.add_argument("--phase25h",type=Path,default=runtime/"phase25h/p1_official_cash_source_reconciliation.json")
    p.add_argument("--parquet-root",type=Path,default=runtime/"data/runtime/parquet")
    p.add_argument("--out",type=Path,default=runtime/"phase25i/real_market_gate_matrix_2024_2025.json")
    a=p.parse_args()
    try:
        sources={x.resolve() for x in (a.db,a.phase24,a.phase25b,a.phase25h)}
        if a.out.is_symlink() or a.out.resolve() in sources:
            raise ValueError("CANNOT_OVERWRITE_SOURCE")
        report=assess(a.db,a.phase24,a.phase25b,a.phase25h,a.parquet_root)
        a.out.parent.mkdir(parents=True,exist_ok=True)
        temp=a.out.with_name(a.out.name+".tmp")
        if temp.is_symlink():
            raise ValueError("UNSAFE_OUTPUT_TEMP_SYMLINK")
        temp.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
        temp.replace(a.out)
    except (OSError,ValueError,TypeError,KeyError,sqlite3.Error):
        print("PHASE25I_BLOCKED: SOURCE_PROVENANCE_OR_DATABASE_ACCESS_FAILED")
        return 2
    print(json.dumps({"status":report["status"],
                      "counts":report["counts"],
                      "blockers":report["blockers"],
                      "walk_forward_executed":False,"Learning_V3_executed":False,
                      "report":str(a.out),"db_modified":False},ensure_ascii=False,indent=2))
    return 0 if not report["blockers"] else 2


if __name__=="__main__":
    raise SystemExit(main())
