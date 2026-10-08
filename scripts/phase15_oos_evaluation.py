from __future__ import annotations

"""Phase 15 research-only OOS evaluation on frozen WF6 + mature WF5 evidence.

* Never computes canonical S15/S16 scores or trains a model.
* Requires a COMPLETE WF6 source and an explicitly selected WF5 evidence batch.
* A snapshot date is excluded UNLESS all recorded WF6 candidates have a
  source-linked mature, matching label and comparable canonical S15 score.
* Ranking metrics are conditional on the selected WF6 cohort. They are NOT
  independently certified full-US market 10X recall or trade P&L.
"""
import argparse
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3

SCHEMA = "MERIDYEN_PHASE15_OOS_AUDIT_V1"
DEFAULT_K = (10, 20)


def _readonly(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"Missing local SQLite source: {path.name}")
    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _has_tables(conn, names):
    existing={r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    absent=sorted(set(names)-existing)
    if absent:
        raise ValueError("Required tables absent: "+", ".join(absent))


def _datetime(value):
    try:
        d=datetime.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid label time") from exc
    if d.tzinfo is None:
        raise ValueError("Timezone-aware label availability required")
    return d.astimezone(timezone.utc)


def _validate_k(ks):
    values=tuple(sorted(set(int(k) for k in ks)))
    if not values or any(k<1 or k>1000 for k in values):
        raise ValueError("K must contain integers from 1 to 1000")
    return values


def _snapshot_metrics(rows, ks):
    # Called only on a fully labelled, verified, READY snapshot cohort.
    chosen=sorted(rows,key=lambda x:(-x["score"],x["security_id"]))
    count=len(chosen)
    winners=sum(r["hit10"] for r in chosen)
    result={"eligible_n":count,"true_10x_n":winners,
            "cohort_base_rate_10x":winners/count,
            "score_leader":chosen[0]["ticker"],
            "at_k":{}}
    for k in ks:
        if k>count:
            result["at_k"][str(k)]={"status":"INSUFFICIENT_COHORT","precision":None,
                                   "recall_within_source_cohort":None}
            continue
        top=chosen[:k]
        hits=sum(x["hit10"] for x in top)
        result["at_k"][str(k)]={
            "status":"EVALUATED", "selected_n":k,"true_10x_in_top_k":hits,
            "precision":hits/k,
            "recall_within_source_cohort":hits/winners if winners else None,
        }
    return result


def evaluate(operational_db,learning_db,*,wf6_run_id,batch_sha256,cutoff,ks=DEFAULT_K):
    ks=_validate_k(ks)
    cutoff=date.fromisoformat(str(cutoff))
    if cutoff>date.today():
        raise ValueError("Cannot evaluate with future cutoff")
    a=_readonly(operational_db)
    b=_readonly(learning_db)
    try:
        _has_tables(a, ("wf6_walk_forward_runs","wf6_walk_forward_folds",
                        "wf6_oos_observations"))
        _has_tables(b, ("learning_v2_wf5_batches",
                        "learning_v2_wf5_mature_labels"))
        run=a.execute("SELECT * FROM wf6_walk_forward_runs WHERE run_id=?",
                      (wf6_run_id,)).fetchone()
        batch=b.execute("SELECT * FROM learning_v2_wf5_batches WHERE digest=?",
                        (batch_sha256,)).fetchone()
        if run is None or run["status"]!="COMPLETE":
            raise ValueError("WF6 run missing or not COMPLETE")
        if batch is None or batch["run_id"]!=run["source_wf5_run_id"]:
            raise ValueError("Mature WF5 batch must match WF6 source run")
        if date.fromisoformat(batch["cutoff"])>cutoff:
            raise ValueError("WF5 evidence batch cutoff is newer than evaluation cutoff")
        if batch["source_pit_verified"]:
            # This bit is not independently sufficient even when nonzero.
            raise ValueError("Untrusted automatic PIT certification flag")
        labels={}
        for row in b.execute("""
            SELECT * FROM learning_v2_wf5_mature_labels
            WHERE digest=?
            ORDER BY signal_date, security_id
        """,(batch_sha256,)):
            identity=(row["security_id"],row["signal_date"])
            if identity in labels:
                raise ValueError("Duplicate source security/date in mature batch")
            label_date=_datetime(row["label_available_at"])
            if label_date.date()<=date.fromisoformat(row["signal_date"]):
                raise ValueError("Mature outcome availability must follow signal")
            if label_date.date()>cutoff:
                continue
            if row["horizon_sessions"]!=252 or row["model_version"] is None:
                raise ValueError("Unexpected mature label contract")
            labels[identity]=row

        folds=a.execute("""SELECT * FROM wf6_walk_forward_folds
            WHERE run_id=? ORDER BY fold_index""",(wf6_run_id,)).fetchall()
        if not folds or any(f["status"]!="COMPLETE" for f in folds):
            raise ValueError("WF6 folds missing or not COMPLETE")
        fold_windows={}
        for fold in folds:
            lo=date.fromisoformat(fold["test_start_date"])
            hi=date.fromisoformat(fold["test_end_date"])
            if hi<lo:
                raise ValueError("Invalid OOS fold window")
            fold_windows[fold["fold_id"]]=(lo,hi)
        observations=a.execute("""SELECT o.*, f.test_start_date, f.test_end_date,
                    f.fold_index
            FROM wf6_oos_observations o
            JOIN wf6_walk_forward_folds f ON o.fold_id=f.fold_id
            WHERE f.run_id=?
            ORDER BY o.as_of_date,o.security_id""",(wf6_run_id,)).fetchall()
        if not observations:
            raise ValueError("WF6 has no OOS records")
        grouped=defaultdict(list)
        seen=set()
        for row in observations:
            ident=(row["security_id"],row["as_of_date"])
            if ident in seen:
                raise ValueError("Overlapping folds or duplicated security/date")
            seen.add(ident)
            d=date.fromisoformat(row["as_of_date"])
            lo,hi=fold_windows[row["fold_id"]]
            if not lo<=d<=hi:
                raise ValueError("OOS observation outside fold test dates")
            grouped[(row["fold_id"],row["as_of_date"])].append(row)

        evaluated=[]
        reasons=Counter()
        total_records=0
        for (fold_id,day),members in sorted(grouped.items(),key=lambda x:x[0][1]):
            candidate=[]
            blockers=Counter()
            for row in members:
                total_records+=1
                label=labels.get((row["security_id"],day))
                score=row["v141_score"]
                if row["outcome_status"]!="READY":
                    blockers["WF6_OUTCOME_NOT_READY"]+=1
                if score is None or row["v141_status"].startswith(("INCONCLUSIVE","BLOCKED")):
                    blockers["WF6_SCORE_NOT_CANONICAL_READY"]+=1
                if label is None:
                    blockers["MISSING_OR_IMMATURE_PROVENANCE_LABEL"]+=1
                if blockers and (
                    row["outcome_status"]!="READY" or score is None or label is None
                ):
                    continue
                if not isinstance(score,(int,float)) or not math.isfinite(score):
                    raise ValueError("Nonfinite WF6 canonical score")
                if label["observation_id"]!=row["source_observation_id"]:
                    raise ValueError("WF6 observation does not match recorded label ID")
                if not math.isclose(float(label["canonical_score"]),float(score),abs_tol=1e-8):
                    raise ValueError("Frozen WF6 score differs from mature WF5 evidence")
                for value, key in (("hit_2x","time_to_2x_sessions"),
                                   ("hit_5x","time_to_5x_sessions"),
                                   ("hit_10x","time_to_10x_sessions")):
                    if row[key]!=label[key]:
                        raise ValueError("WF6 event timing and mature outcome label disagree")
                if not math.isclose(float(row["fm252"]),float(label["fm252"]),abs_tol=1e-8):
                    raise ValueError("WF6 outcome magnitude mismatch")
                candidate.append({"security_id":row["security_id"],
                                  "ticker":row["ticker"],"score":float(score),
                                  "hit10":int(label["hit_10x"])})
            if blockers or len(candidate)!=len(members):
                for name,n in blockers.items():
                    reasons[name]+=n
                reasons["EXCLUDED_INCOMPLETE_SNAPSHOT"]+=1
                continue
            stats=_snapshot_metrics(candidate,ks)
            evaluated.append({
                "fold_id":fold_id,"date":day,
                "fold_index":int(members[0]["fold_index"]),**stats
            })
        top_metrics={}
        for k in ks:
            passing=[d for d in evaluated
                     if d["at_k"][str(k)]["status"]=="EVALUATED"]
            total_selected=k*len(passing)
            hits=sum(d["at_k"][str(k)]["true_10x_in_top_k"] for d in passing)
            available_winners=sum(d["true_10x_n"] for d in passing)
            top_metrics[str(k)]={
                "status":"EVALUATED_CONDITIONAL" if passing else "NO_COMPLETE_ELIGIBLE_DATE",
                "dates_evaluated":len(passing),
                "selected_n":total_selected,
                "10x_hits":hits,
                "precision_at_k":hits/total_selected if total_selected else None,
                "recall_in_evaluated_source_cohort":(
                    hits/available_winners if available_winners else None
                ),
                "universe_10x_recall":None,
            }
        total_eligible=sum(r["eligible_n"] for r in evaluated)
        total_winners=sum(r["true_10x_n"] for r in evaluated)
        summary={
            "schema":SCHEMA,
            "status":"OOS_RESEARCH_DIAGNOSTIC_NOT_PIT_CERTIFIED" if evaluated
                 else "BLOCKED_NO_FULLY_MATURE_SNAPSHOT",
            "wf6_run_id":wf6_run_id,"source_wf5_run_id":run["source_wf5_run_id"],
            "source_batch_sha256":batch_sha256,
            "as_of":cutoff.isoformat(),
            "oos_folds":len(folds),
            "all_oos_observations":total_records,
            "dates_seen":len(grouped),"fully_labelled_dates":len(evaluated),
            "eligible_observations_on_complete_dates":total_eligible,
            "mature_winners_10x_on_complete_dates":total_winners,
            "conditional_base_rate_10x":total_winners/total_eligible if total_eligible else None,
            "precision_at_k":top_metrics,
            "exclusion_reasons":dict(reasons),
            "source_independently_pit_verified":False,
            "oos_performance_certified":False,
            "matched_control_peer_benchmark":"NOT_AVAILABLE",
            "trading_costs_applied":False,
            "model_training_performed":False,
            "canonical_models_modified":False,
            "warning":"Conditional ranking diagnostics, not independent PIT validation, full-US recall or executable trading P&L.",
            "dates":evaluated,
        }
        summary["report_sha256"]=hashlib.sha256(
            json.dumps(summary,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
        ).hexdigest()
        return summary
    finally:
        a.close()
        b.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--operational-db",type=Path,required=True)
    p.add_argument("--learning-db",type=Path,required=True)
    p.add_argument("--wf6-run-id",required=True)
    p.add_argument("--wf5-batch-sha256",required=True)
    p.add_argument("--cutoff",required=True)
    p.add_argument("--k",nargs="+",type=int,default=list(DEFAULT_K))
    p.add_argument("--out",type=Path,default=Path("data/runtime/phase15_oos_audit.json"))
    args=p.parse_args()
    try:
        result=evaluate(args.operational_db,args.learning_db,
                        wf6_run_id=args.wf6_run_id,
                        batch_sha256=args.wf5_batch_sha256,
                        cutoff=args.cutoff,ks=args.k)
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False)+"\n",encoding="utf-8")
        print(json.dumps({"status":result["status"],"out":str(args.out),
                          "fully_labelled_dates":result["fully_labelled_dates"]},
                         ensure_ascii=False))
        return 0 if result["fully_labelled_dates"] else 2
    except (ValueError,sqlite3.Error,OSError) as exc:
        p.exit(2,"PHASE15_OOS_BLOCKED: "+str(exc)+"\n")


if __name__=="__main__":
    raise SystemExit(main())
