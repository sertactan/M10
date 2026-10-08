from __future__ import annotations

"""Read-only export of COMPLETE WF5 mature evidence + dated canonical features.

All candidates in one WF5 snapshot date must be fully scored, source-linked,
mature and have all requested PIT features, otherwise exclude that date.
No learned model/predictions, downloads or database mutations.
"""
import argparse
from collections import Counter,defaultdict
from datetime import date,datetime,time,timezone
import json
import math
from pathlib import Path
import sqlite3

from core.learning_v3.challenger import SCHEMA,SAFE_FEATURE,BAD_FEATURE,_timestamp,_finite
from core.learning_v2.wf5_outcome_bridge import READY_STATUSES


def _conn(path):
    path=Path(path)
    if not path.is_file():
        raise ValueError("Missing local M10 SQLite evidence")
    c=sqlite3.connect(path.resolve().as_uri()+"?mode=ro",uri=True)
    c.row_factory=sqlite3.Row
    return c


def export(operational_db,learning_db,*,wf5_run_id,batch_sha256,features,cutoff):
    limit=date.fromisoformat(str(cutoff))
    if limit>datetime.now(timezone.utc).date():
        raise ValueError("Future evaluation date")
    if not (1<=len(features)<=12 and len(set(features))==len(features)):
        raise ValueError("Require 1–12 distinct explicit feature keys")
    if any(not SAFE_FEATURE.fullmatch(f) or BAD_FEATURE.search(f) for f in features):
        raise ValueError("Forbidden or malformed feature key")
    a,b=_conn(operational_db),_conn(learning_db)
    try:
        ra=a.execute("SELECT status FROM wf5_replay_runs WHERE run_id=?",(wf5_run_id,)).fetchone()
        rb=b.execute("SELECT run_id,cutoff FROM learning_v2_wf5_batches WHERE digest=?",(batch_sha256,)).fetchone()
        if ra is None or ra["status"]!="COMPLETE":
            raise ValueError("WF5 source must be COMPLETE")
        if rb is None or rb["run_id"]!=wf5_run_id or date.fromisoformat(rb["cutoff"])>limit:
            raise ValueError("Mature-label batch is unavailable or source run differs")
        wf5=a.execute("""SELECT observation_id,security_id,ticker,as_of_date,
                 v141_score,v141_status,outcome_status
                 FROM wf5_replay_observations WHERE run_id=?
                 ORDER BY as_of_date,security_id""",(wf5_run_id,)).fetchall()
        label_rows=list(b.execute(
            "SELECT * FROM learning_v2_wf5_mature_labels WHERE digest=?",(batch_sha256,)))
        labels={(r["security_id"],r["signal_date"]):r for r in label_rows}
        if len(labels)!=len(label_rows):
            raise ValueError("Duplicate security/date in mature-label evidence batch")
        if not wf5:
            raise ValueError("No historical candidate observations")
        bydate=defaultdict(list)
        for row in wf5:
            bydate[row["as_of_date"]].append(row)
        final=[]; omitted=Counter()
        for day,members in sorted(bydate.items()):
            if day>limit.isoformat():
                omitted["FUTURE_SIGNAL_DATE"]+=1
                continue
            result=[]
            reasons=Counter()
            for row in members:
                key=(row["security_id"],day)
                label=labels.get(key)
                if (row["outcome_status"]!="READY" or row["v141_score"] is None
                    or row["v141_status"] not in READY_STATUSES):
                    reasons["NOT_CANONICAL_READY"]+=1
                    continue
                if label is None:
                    reasons["NOT_MATURE_OR_UNVERIFIED_LABEL"]+=1
                    continue
                if label["observation_id"]!=row["observation_id"]:
                    raise ValueError("WF5 observation identity mismatch")
                if (label["model_version"]!="S15.3_V1.4.1_CANONICAL_COMPLETION_2026-10-07"
                    or not math.isclose(_finite(label["canonical_score"]),
                                        _finite(row["v141_score"]),abs_tol=1e-8)):
                    raise ValueError("Frozen S15 score identity mismatch")
                label_time=_timestamp(label["label_available_at"])
                if label_time.date()>limit or label_time.date()<=date.fromisoformat(day):
                    reasons["LABEL_NOT_MATURE_AT_CUTOFF"]+=1
                    continue
                attributes={}
                asof=datetime.combine(date.fromisoformat(day),time.max,tzinfo=timezone.utc)
                for name in features:
                    # The native feature repository keeps multiple point-in-time
                    # revisions. Select most recent feature snapshot with data
                    # explicitly available no later than the signal date.
                    alternatives=a.execute("""
                        SELECT feature_key,value,available_at,feature_as_of,
                               source_phase,source_ref,quality_status
                        FROM canonical_model_features
                        WHERE security_id=? AND feature_key=?
                        ORDER BY feature_as_of DESC,available_at DESC
                    """,(row["security_id"],name))
                    chosen=None
                    for candidate in alternatives:
                        if candidate["source_phase"] not in (
                            "PHASE1_UNIVERSE","PHASE2_PRICE",
                            "PHASE3_FUNDAMENTAL","DERIVED_CANONICAL"):
                            continue
                        try:
                            available=_timestamp(candidate["available_at"])
                            feature_time=_timestamp(candidate["feature_as_of"])
                            value=_finite(candidate["value"])
                        except (ValueError,TypeError):
                            continue
                        if (available>asof or feature_time>asof or available>feature_time
                            or not str(candidate["source_ref"]).strip()
                            or str(candidate["quality_status"]).upper().startswith(
                                ("BLOCKED","INVALID","REJECTED","MISSING"))):
                            continue
                        chosen={"value":value,"available_at":available.isoformat(),
                                "source_ref":candidate["source_ref"]}
                        break
                    if chosen is None:
                        reasons["FEATURE_MISSING_OR_NOT_PIT_"+name]+=1
                        break
                    attributes[name]=chosen
                if len(attributes)!=len(features):
                    continue
                result.append({
                    "source_run_id":wf5_run_id,
                    "security_id":row["security_id"],"ticker":row["ticker"],
                    "signal_date":day,"canonical_score":float(row["v141_score"]),
                    "label_available_at":label_time.isoformat(),
                    "hit_10x":bool(label["hit_10x"]),
                    "outcome_hash":label["outcome_hash"],
                    "features":attributes,
                    "snapshot_expected_count":len(members),
                })
            if reasons or len(result)!=len(members):
                omitted["INCOMPLETE_COHORT_DATE"]+=1
                omitted.update(reasons)
            else:
                final.extend(result)
        if not final:
            raise ValueError("No complete mature, PIT-featured WF5 dates to export")
        return {
            "schema":SCHEMA,
            "source_run_id":wf5_run_id,
            "source_batch_sha256":batch_sha256,
            "feature_names":list(features),
            "rows":final,
            "source_data_pit_independently_certified":False,
            "omitted_dates":dict(omitted),
            "training_and_promotion_executed":False,
            "note":"Private experiment input only; no independent full-universe PIT or delisting certification.",
        }
    finally:
        a.close();b.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--operational-db",type=Path,required=True)
    p.add_argument("--learning-db",type=Path,required=True)
    p.add_argument("--wf5-run-id",required=True)
    p.add_argument("--wf5-batch-sha256",required=True)
    p.add_argument("--feature-keys",nargs="+",required=True,
                   help="Feature keys already in M10 canonical_model_features; e.g. d01 f54_dil")
    p.add_argument("--cutoff",required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    try:
        doc=export(args.operational_db,args.learning_db,wf5_run_id=args.wf5_run_id,
                   batch_sha256=args.wf5_batch_sha256,features=args.feature_keys,
                   cutoff=args.cutoff)
        args.out.parent.mkdir(parents=True,exist_ok=True)
        if args.out.exists():
            raise ValueError("Refusing overwrite of dated training source")
        args.out.write_text(json.dumps(doc,indent=2,ensure_ascii=False,allow_nan=False)+"\n")
        print(json.dumps({"status":"PRIVATE_FEATURE_EXPORT_ONLY",
                          "output":str(args.out),"rows":len(doc["rows"]),
                          "omitted":doc["omitted_dates"]},ensure_ascii=False))
    except (OSError,ValueError,sqlite3.Error) as exc:
        p.exit(2,"LEARNING_V3_FEATURE_EXPORT_BLOCKED: "+str(exc)+"\n")


if __name__=="__main__":
    main()
