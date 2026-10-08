from __future__ import annotations

"""Phase16: one-shot, schedulable Learning V2 evidence/backup cycle.

This command does NOT install a background service and does not run itself.
Windows Task Scheduler must be explicitly configured by the user.
No market-data sources, canonical score changes, or ML training here.
"""
import argparse
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
from uuid import uuid4

from core.learning_v2.journal import connect, audit, backup, learn_backtest
from core.learning_v2.wf5_outcome_bridge import ingest_wf5, audit_wf5_learning
from scripts.import_research_pilot import import_pilot,audit_research
from scripts.sync_learning_backup import upload_verified


def cycle(learning_db,backup_dir,*,backtest=None,research_bundle=None,
          operational_db=None,wf5_run_id=None,cutoff=None,
          cloud_remote=None,execute_cloud=False,initialize=False):
    db=Path(learning_db)
    backup_dir=Path(backup_dir)
    if bool(operational_db)!=bool(wf5_run_id):
        raise ValueError("Both operational DB and WF5 run ID are required")
    if execute_cloud and not cloud_remote:
        raise ValueError("Cloud authorization requires a crypt remote")
    if not db.is_file() and not initialize:
        raise ValueError("Learning SQLite missing: run learning_v2.py init explicitly")
    lock=db.with_suffix(db.suffix+".cycle.lock")
    lock.parent.mkdir(parents=True,exist_ok=True)
    # Atomic exclusive create rejects overlapping Task Scheduler invocations.
    try:
        fd=os.open(lock,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except FileExistsError as exc:
        raise ValueError("A learning cycle already owns the local lock") from exc
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as writer:
            writer.write(json.dumps({"started_at":datetime.now(timezone.utc).isoformat(),
                                    "pid":os.getpid()})+"\n")
        if initialize and not db.is_file():
            conn=connect(db)
            conn.close()
        results=[]
        effective_cutoff=cutoff or datetime.now(timezone.utc).date().isoformat()
        if date.fromisoformat(effective_cutoff)>datetime.now(timezone.utc).date():
            raise ValueError("Cannot learn from a future date")
        if backtest:
            results.append({"source":"backtest","result":learn_backtest(db,backtest,effective_cutoff)})
        if research_bundle:
            results.append({"source":"sec_research","result":import_pilot(db,research_bundle)})
        if operational_db:
            results.append({"source":"mature_wf5","result":ingest_wf5(
                operational_db,db,run_id=wf5_run_id,cutoff=effective_cutoff)})
        # Always audit historical status; audit alone cannot promote a model.
        audit_result=audit(db)
        research_result=audit_research(db)
        wf5_result=audit_wf5_learning(db)
        backup_result=backup(db,backup_dir)
        cloud_status="DISABLED_LOCAL_ONLY"
        if cloud_remote:
            cloud_status="NOT_EXECUTED_REMOTE_DRY_RUN"
            if execute_cloud:
                cloud_status=upload_verified(Path(backup_result["manifest_file"]),cloud_remote)["status"]
        report={
            "schema":"MERIDYEN_PHASE16_CYCLE_V1",
            "status":"COMPLETE_LOCAL_BACKUP" if not execute_cloud
                    else "COMPLETE_CLOUD_ROUNDTRIP_VERIFIED",
            "cycle_id":uuid4().hex,
            "cutoff":effective_cutoff,
            "inputs_imported":results,
            "audits":{
                "historical":audit_result,
                "sec_research":research_result,
                "wf5_maturity":wf5_result,
            },
            "snapshot":{
                "manifest":backup_result["manifest_file"],
                "sha256":backup_result["sha256"],
                "integrity":backup_result["integrity"],
            },
            "cloud_status":cloud_status,
            "model_training_performed":False,
            "canonical_s15_s16_modified":False,
            "not_pit_certified":True,
        }
        local_report=backup_dir/f"phase16-cycle-{report['cycle_id']}.json"
        local_report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        report["local_report"]=str(local_report)
        return report
    finally:
        # No auto-deletion of another process's lock. Only the owner created
        # this lock, and only this invocation releases it.
        lock.unlink(missing_ok=True)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--learning-db",type=Path,required=True)
    ap.add_argument("--backup-dir",type=Path,required=True)
    ap.add_argument("--cutoff",help="YYYY-MM-DD, defaults to current UTC date")
    ap.add_argument("--backtest",type=Path)
    ap.add_argument("--research-bundle",type=Path)
    ap.add_argument("--operational-db",type=Path)
    ap.add_argument("--wf5-run-id")
    ap.add_argument("--cloud-crypt-remote",help="Previously configured rclone crypt remote name")
    ap.add_argument("--execute-cloud",action="store_true",
                    help="Explicit permission to upload and verify cloud snapshot")
    ap.add_argument("--initialize",action="store_true",
                    help="Explicit permission to initialize a fresh empty Learning V2 database")
    args=ap.parse_args()
    try:
        result=cycle(
            args.learning_db,args.backup_dir,
            cutoff=args.cutoff,backtest=args.backtest,research_bundle=args.research_bundle,
            operational_db=args.operational_db,wf5_run_id=args.wf5_run_id,
            cloud_remote=args.cloud_crypt_remote,execute_cloud=args.execute_cloud,
            initialize=args.initialize)
        print(json.dumps({
            "status":result["status"],
            "cycle_id":result["cycle_id"],
            "local_report":result["local_report"],
            "cloud_status":result["cloud_status"],
            "training":False},ensure_ascii=False))
        return 0
    except (ValueError,OSError) as exc:
        ap.exit(2,"PHASE16_CYCLE_BLOCKED: "+str(exc)+"\n")


if __name__=="__main__":
    raise SystemExit(main())
