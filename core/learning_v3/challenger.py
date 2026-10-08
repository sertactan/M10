from __future__ import annotations

"""Phase 17 V3: deterministic research-only ML challenger, NOT S15 replacement.

No network, trading, sklearn/pickle, mutations of canonical formulas, model
deployment, or ChatGPT fine-tuning. Every feature must have dated evidence.
Only fully labelled snapshot cohorts are accepted. Training labels must have
been available BEFORE the first OOS signal date.
"""
from collections import Counter, defaultdict
from datetime import date, datetime, time, timezone
import hashlib
import json
import math
import re

SCHEMA = "MERIDYEN_V3_DATED_COHORT_V1"
ENGINE = "MERIDYEN_LEARNING_V3_EXPERIMENT_V1"
BAD_FEATURE = re.compile(r"(?:^|_)(?:target|label|hit|outcome|future|forward|fm252|return|time_to)(?:_|$)")
SAFE_FEATURE = re.compile(r"^[a-z][a-z0-9_]{2,63}$")


def _timestamp(value):
    try:
        v=datetime.fromisoformat(str(value).replace("Z","+00:00"))
        if v.tzinfo is None:
            raise ValueError("timezone required")
        return v.astimezone(timezone.utc)
    except (ValueError,TypeError) as exc:
        raise ValueError("Invalid or timezone-naive availability time") from exc


def _finite(value):
    if isinstance(value,bool) or not isinstance(value,(float,int)):
        raise ValueError("Numeric feature/score required")
    v=float(value)
    if not math.isfinite(v):
        raise ValueError("Nonfinite feature/score")
    return v


def _compact_hash(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,ensure_ascii=False,
                                     separators=(",",":"),allow_nan=False).encode()).hexdigest()


def validate_dataset(data, *, cutoff):
    cutoff=date.fromisoformat(str(cutoff))
    if cutoff>datetime.now(timezone.utc).date():
        raise ValueError("Future evaluation cutoff")
    if not isinstance(data,dict) or data.get("schema")!=SCHEMA:
        raise ValueError("Unrecognized dataset schema")
    features=data.get("feature_names")
    if (not isinstance(features,list) or not (1<=len(features)<=12)
        or any(not isinstance(f,str) or not SAFE_FEATURE.fullmatch(f)
               or BAD_FEATURE.search(f) for f in features)
        or len(set(features))!=len(features)):
        raise ValueError("Feature allowlist is invalid or contains label-derived fields")
    rows=data.get("rows")
    if not isinstance(rows,list) or not rows:
        raise ValueError("Dated candidate rows missing")
    run_id=data.get("source_run_id")
    if not isinstance(run_id,str) or not run_id.strip():
        raise ValueError("Missing source WF5 run ID")
    seen=set(); grouped=defaultdict(list); validated=[]
    for row in rows:
        if not isinstance(row,dict):
            raise ValueError("Invalid record")
        signal=date.fromisoformat(str(row["signal_date"]))
        identity=(str(row["security_id"]), signal.isoformat())
        if not identity[0] or identity in seen:
            raise ValueError("Duplicate or missing security ID/date")
        seen.add(identity)
        label_time=_timestamp(row["label_available_at"])
        if label_time.date()<=signal or label_time.date()>cutoff:
            raise ValueError("Censored/immature label or label future leakage")
        if not isinstance(row.get("hit_10x"),bool):
            raise ValueError("10X label must be boolean")
        score=_finite(row["canonical_score"])
        if not 0<=score<=100:
            raise ValueError("Canonical score out of range")
        if str(row.get("source_run_id"))!=run_id:
            raise ValueError("Inconsistent canonical source run")
        digest=row.get("outcome_hash")
        if not isinstance(digest,str) or not re.fullmatch(r"[0-9a-f]{64}",digest):
            raise ValueError("Missing authoritative outcome hash")
        evidence=row.get("features")
        if not isinstance(evidence,dict) or set(evidence)!=set(features):
            raise ValueError("Incomplete feature/evidence vector")
        values=[]
        for f in features:
            e=evidence[f]
            if not isinstance(e,dict) or not str(e.get("source_ref","")).strip():
                raise ValueError("Feature has no authoritative source")
            observed_at=_timestamp(e["available_at"])
            if observed_at>datetime.combine(signal,time.max,tzinfo=timezone.utc):
                raise ValueError("Lookahead feature availability")
            values.append(_finite(e["value"]))
        expected=row.get("snapshot_expected_count")
        if type(expected)!=int or expected<1:
            raise ValueError("No source cohort completeness count")
        v={"security_id":identity[0],"signal_date":signal.isoformat(),
           "score":score,"y":int(row["hit_10x"]),
           "label_time":label_time,"x":values,"expected":expected}
        grouped[v["signal_date"]].append(v)
        validated.append(v)
    for day,group in grouped.items():
        expected={r["expected"] for r in group}
        if len(expected)!=1 or len(group)!=next(iter(expected)):
            raise ValueError(f"Incomplete labelled snapshot cohort: {day}")
    return features,sorted(validated,key=lambda r:(r["signal_date"],r["security_id"])),grouped


def _model(train, l2=0.02, rounds=650, step=0.07):
    """Stable bounded ridge-logistic with train-only feature normalization."""
    matrix=[[r["score"]/100]+r["x"] for r in train]
    columns=len(matrix[0])
    means=[sum(x[j] for x in matrix)/len(matrix) for j in range(columns)]
    scales=[max((sum((x[j]-means[j])**2 for x in matrix)/len(matrix))**.5,1e-8)
            for j in range(columns)]
    normalized=[[max(-6,min(6,(x[j]-means[j])/scales[j])) for j in range(columns)]
                for x in matrix]
    weights=[0.0]*columns
    positives=sum(r["y"] for r in train)
    if positives==0 or positives==len(train):
        raise ValueError("Training labels contain only one class")
    prior=max(0.01,min(0.99,positives/len(train)))
    bias=math.log(prior/(1-prior))
    for _ in range(rounds):
        grad=[0.0]*columns;gb=0.0
        for x,r in zip(normalized,train):
            z=max(-30,min(30,bias+sum(w*v for w,v in zip(weights,x))))
            prediction=1/(1+math.exp(-z))
            error=prediction-r["y"]
            gb+=error
            for j in range(columns):
                grad[j]+=error*x[j]
        n=len(train)
        bias-=step*gb/n
        for j in range(columns):
            weights[j]-=step*(grad[j]/n+l2*weights[j])
    return {"weights":weights,"bias":bias,"means":means,"scales":scales,
            "features":["s15_canonical_score"]+list(range(columns-1))}


def _prob(model, record):
    x=[record["score"]/100]+record["x"]
    z=model["bias"]+sum(
        w*max(-6,min(6,(v-m)/s))
        for w,v,m,s in zip(model["weights"],x,model["means"],model["scales"]))
    return 1/(1+math.exp(-max(-30,min(30,z))))


def _score_eval(test, probabilities, *, k):
    grouped=defaultdict(list)
    for row in test:
        grouped[row["signal_date"]].append(row)
    n_dates=0; selected=0;cb=0; cc=0;winners=0
    for day,members in sorted(grouped.items()):
        if len(members)<k:
            continue
        n_dates+=1;selected+=k
        baseline=sorted(members,key=lambda r:(-r["score"],r["security_id"]))[:k]
        challenger=sorted(members,key=lambda r:(-probabilities[(r["security_id"],day)],
                                                r["security_id"]))[:k]
        cb+=sum(r["y"] for r in baseline)
        cc+=sum(r["y"] for r in challenger)
        winners+=sum(r["y"] for r in members)
    return {"k":k,"dates_evaluated":n_dates,"selected":selected,
            "s15_baseline_hits":cb,"challenger_hits":cc,
            "s15_precision_at_k":cb/selected if selected else None,
            "challenger_precision_at_k":cc/selected if selected else None,
            "precision_delta_pp":100*(cc-cb)/selected if selected else None,
            "cohort_recall_baseline":cb/winners if winners else None,
            "cohort_recall_challenger":cc/winners if winners else None,
            "full_us_market_recall":None}


def experiment(data, *, cutoff, k=10, min_train=100, min_test=40,
               min_test_dates=3, min_positive=8):
    """One truly chronological holdout; no shuffled random stock-level split.

    A label from training may be used only if its availability time precedes
    the first OOS signal. Test labels are evaluated only as of user cutoff.
    """
    if not 1<=k<=1000 or min_train<2 or min_test<2:
        raise ValueError("Invalid evaluation thresholds")
    features,rows,grouped=validate_dataset(data,cutoff=cutoff)
    dates=sorted(grouped)
    if len(dates)<min_test_dates+2:
        raise ValueError("Insufficient independent snapshot dates")
    split=max(1,min(len(dates)-min_test_dates,int(len(dates)*.7)))
    first_test=date.fromisoformat(dates[split])
    training=[r for r in rows if r["signal_date"]<dates[split]
              and r["label_time"]<datetime.combine(first_test,time.min,tzinfo=timezone.utc)]
    testing=[r for r in rows if r["signal_date"]>=dates[split]]
    positive=sum(r["y"] for r in training)
    if (len(training)<min_train or len(testing)<min_test
        or positive<min_positive or len(training)-positive<min_positive):
        raise ValueError("Not enough matured, available-before-OOS training evidence")
    if len({r["signal_date"] for r in testing})<min_test_dates:
        raise ValueError("Insufficient independent OOS test dates")
    model=_model(training)
    model["features"]=["s15_canonical_score"]+features
    probabilities={(r["security_id"],r["signal_date"]):_prob(model,r) for r in testing}
    metrics=_score_eval(testing,probabilities,k=k)
    if metrics["dates_evaluated"]<min_test_dates:
        raise ValueError("Insufficient complete OOS dates with at least K candidates")
    results={
        "schema":ENGINE,"status":"EXPERIMENTAL_CHALLENGER_NOT_DEPLOYED",
        "source_run_id":data["source_run_id"],"source_sha256":_compact_hash(data),
        "as_of":str(cutoff),"first_oos_date":dates[split],
        "training_rows":len(training),"test_rows":len(testing),
        "training_positive":positive,
        "training_latest_label_available_at":max(r["label_time"] for r in training).isoformat(),
        "model":model,"model_sha256":_compact_hash(model),
        "metrics":metrics,"baseline":"FROZEN_S15_V1_4_1",
        "pit_independently_verified":False,
        "production_promotion_allowed":False,"code_mutation_performed":False,
        "new_trades_executed":False,
        "blockers":[
            "INDEPENDENT_FULL_UNIVERSE_PIT_AUDIT_NOT_VERIFIED",
            "MULTIPLE_INDEPENDENT_MARKET_REGIME_OOS_TESTS_REQUIRED",
            "MATCHED_CONTROLS_AND_TRANSACTION_COSTS_REQUIRED",
            "OWNER_REVIEW_AND_NEW_MODEL_VERSION_REQUIRED",
        ],
        "note":"Conditional OOS on complete supplied cohorts. Not full-market 10X recall, profitability, or a new canonical S15 score.",
    }
    results["report_sha256"]=_compact_hash(results)
    return results
