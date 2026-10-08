from __future__ import annotations

"""Local-first M10 runtime, real-data, and optional Drive readiness audit.

NO cloud upload, network access, source DB creation, market-data downloading,
WF9 activation, or automatic model promotion. 2013-2024 PIT status remains
BLOCKED until independently evidenced by the real Windows environment.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3

from scripts.phase13_readiness_report import evaluate as phase13
from scripts.phase14_dataset_audit import audit as phase14

SCHEMA="MERIDYEN_LOCAL_FIRST_ACTIVATION_V1"
WINDOW=("2013-01-01","2024-12-31")


def _sqlite_probe(path):
    p=Path(path)
    out={"present":p.is_file(),"quick_check":"NOT_CHECKED",
         "tables":[],"learning_mature_labels":None,"wf5_runs_complete":None,
         "wf6_runs_complete":None}
    if not p.is_file():
        return out
    try:
        conn=sqlite3.connect(p.resolve().as_uri()+"?mode=ro",uri=True)
        conn.row_factory=sqlite3.Row
        try:
            c=conn.execute("PRAGMA quick_check").fetchone()
            out["quick_check"]=str(c[0]) if c else "NO_RESULT"
            tables={row["name"] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            out["tables"]=sorted(tables.intersection({
                "universe_snapshot_membership","canonical_price_selection",
                "fundamental_facts_source","canonical_model_features",
                "wf5_replay_runs","wf6_walk_forward_runs",
                "learning_v2_wf5_mature_labels","learning_v2_research_sources",
                "learning_v2_sources",
            }))
            for table,field in [
                ("learning_v2_wf5_mature_labels","learning_mature_labels"),
                ("wf5_replay_runs","wf5_runs_complete"),
                ("wf6_walk_forward_runs","wf6_runs_complete"),
            ]:
                if table not in tables:
                    continue
                if table in ("wf5_replay_runs","wf6_walk_forward_runs"):
                    sql=f"SELECT COUNT(*) FROM {table} WHERE status='COMPLETE'"
                else:
                    sql="SELECT COUNT(*) FROM learning_v2_wf5_mature_labels"
                out[field]=int(conn.execute(sql).fetchone()[0])
        finally:
            conn.close()
    except (sqlite3.Error,OSError,ValueError) as exc:
        out["quick_check"]="ERROR_"+type(exc).__name__
    return out


def _price_files(root, max_files=250000):
    p=Path(root)
    report={"present":p.is_dir(),"parquet_files":0,
            "total_bytes":0,"inventory_complete":False,
            "unsafe_symlinks":0,"non_parquet_files":0}
    if not p.is_dir():
        return report
    try:
        if p.is_symlink():
            report["unsafe_symlinks"]=1
            return report
        for file in p.rglob("*"):
            if file.is_symlink():
                report["unsafe_symlinks"]+=1
                continue
            if not file.is_file():
                continue
            if file.suffix.lower()!=".parquet":
                report["non_parquet_files"]+=1
                continue
            report["parquet_files"]+=1
            report["total_bytes"]+=file.stat().st_size
            if report["parquet_files"]>max_files:
                report["inventory_limit_reached"]=True
                return report
        report["inventory_complete"]=True
    except OSError as exc:
        report["error_class"]=type(exc).__name__
    return report


def inspect(*,runtime_root,db=None,learning_db=None,parquet=None,
            start=WINDOW[0],end=WINDOW[1],price_checks=250000):
    """Return a truthful operator report, never a PIT certificate."""
    root=Path(runtime_root).expanduser().resolve()
    market=Path(db) if db is not None else root/"data/runtime/operational.db"
    learning=(Path(learning_db) if learning_db is not None
              else root/"data/runtime/meridyen_learning.sqlite3")
    prices=Path(parquet) if parquet is not None else root/"data/runtime/parquet"
    market_probe=_sqlite_probe(market)
    learn_probe=_sqlite_probe(learning)
    inventory=_price_files(prices)
    p13=phase13(market,start,end)
    p14=phase14(market,prices,start,end,price_checks=price_checks)
    blockers=[]
    if not market_probe["present"]:
        blockers.append("REAL_M10_OPERATIONAL_DB_NOT_ACCESSIBLE")
    if market_probe["quick_check"]!="ok" and market_probe["present"]:
        blockers.append("OPERATIONAL_DB_INTEGRITY_NOT_OK")
    if not learn_probe["present"]:
        blockers.append("LEARNING_V2_LOCAL_DB_MISSING")
    if not inventory["present"] or inventory["parquet_files"]==0:
        blockers.append("NO_LOCAL_CANONICAL_PARQUET_DATA")
    if inventory["unsafe_symlinks"] or not inventory["inventory_complete"]:
        blockers.append("PRICE_FILE_INVENTORY_NOT_COMPLETE")
    if p13["status"]!="PREFLIGHT_READY_NOT_ACTIVATED":
        blockers.append("PHASE13_WF9_PREFLIGHT_BLOCKED")
    if p14["status"]!="PREFLIGHT_INPUT_COVERAGE_ASSERTED_NOT_PIT_CERTIFIED":
        blockers.append("PHASE14_DATASET_PIT_INPUT_AUDIT_BLOCKED")
    if not learn_probe["learning_mature_labels"]:
        blockers.append("NO_MATURE_WF5_LEARNING_OUTCOMES")
    # A green technical preflight is not independent PIT/corporate action
    # certification nor genuine WF9 activation.
    actions=[]
    if not market_probe["present"]:
        actions.append("Find the active M10 writable runtime on Windows and pass --runtime-root or --db explicitly")
    elif "PHASE13_WF9_PREFLIGHT_BLOCKED" in blockers:
        actions.append("Run historical PIT universe and SEC/adjusted-price bootstrap; examine Phase13 missing-month report")
    if "PHASE14_DATASET_PIT_INPUT_AUDIT_BLOCKED" in blockers:
        actions.append("Check individual sources, physical Parquet partitions, delistings, adjusted bars and filing available_at")
    if not learn_probe["present"]:
        actions.append("Initialize the private local Learning V2 SQLite using scripts/learning_v2.py init")
    if not learn_probe["learning_mature_labels"]:
        actions.append("After verified COMPLETE WF5 replay, import 252-session mature labels via wf5-labels-import")
    actions.append("Drive archival is optional: configure rclone crypt locally, test encrypted upload AND recovery before declaring it active")
    actions.append("After full PIT + WF9 audit, run Phase15 OOS and Phase17 V3 on complete dated cohorts")
    return {
        "schema":SCHEMA,
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "window":{"start":start,"end":end},
        "status":"LOCAL_ACTIVATION_EVIDENCE_REQUIRED" if blockers
                 else "TECHNICAL_INPUTS_PRESENT_INDEPENDENT_AUDIT_REQUIRED",
        "runtime_root":str(root),
        "market_database":market_probe,
        "learning_database":learn_probe,
        "local_parquet":inventory,
        "phase13":{"status":p13["status"],"blockers":p13.get("blockers",[]),
                   "coverage":p13.get("coverage")},
        "phase14":{"status":p14["status"],"blockers":p14.get("blockers",[]),
                   "missing_snapshot_dates":p14.get("missing_snapshot_dates",[]),
                   "physical_prices":p14.get("physical_prices",{})},
        "drive":{
            "required_for_database_queries":False,
            "recommended_role":"OPTIONAL_ENCRYPTED_OFFSITE_BACKUP",
            "remote_connected_or_tested":False,
            "cloud_data_present_not_assumed":True,
        },
        "blockers":blockers,
        "next_actions":actions,
        "pit_independently_certified":False,
        "wf9_production_activated":False,
        "model_training_performed":False,
        "canonical_formula_modified":False,
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--runtime-root",type=Path,default=Path(
        os.getenv("S153_RUNTIME_ROOT") or Path(__file__).resolve().parents[1]))
    p.add_argument("--db",type=Path)
    p.add_argument("--learning-db",type=Path)
    p.add_argument("--parquet-root",type=Path)
    p.add_argument("--start",default=WINDOW[0])
    p.add_argument("--end",default=WINDOW[1])
    p.add_argument("--price-checks",type=int,default=250000)
    p.add_argument("--out",type=Path,default=Path("data/runtime/phase18/activation_report.json"))
    p.add_argument("--report-only",action="store_true",
                   help="Exit 0 for GitHub-hosted diagnostic artifacts even when blocked")
    a=p.parse_args()
    try:
        result=inspect(runtime_root=a.runtime_root,db=a.db,learning_db=a.learning_db,
                       parquet=a.parquet_root,start=a.start,end=a.end,
                       price_checks=a.price_checks)
        a.out.parent.mkdir(parents=True,exist_ok=True)
        a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps({"status":result["status"],"blockers":result["blockers"],
                          "report":str(a.out),"drive_required":False},ensure_ascii=False))
        return 0 if a.report_only or not result["blockers"] else 2
    except (ValueError,OSError) as exc:
        p.exit(2,"MERIDYEN_RUNTIME_INTAKE_BLOCKED: "+str(exc)+"\n")


if __name__=="__main__":
    raise SystemExit(main())
