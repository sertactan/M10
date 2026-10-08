from datetime import datetime,timedelta,timezone
import pytest
from core.learning_v3.challenger import SCHEMA,experiment

def sample(feature="D01"):
    origin=datetime(2013,1,1,tzinfo=timezone.utc)
    rows=[]
    for i in range(28):
        d=origin+timedelta(days=i*90)
        for j in range(5):
            rows.append(dict(source_run_id="WF5TEST",security_id=f"{i}-{j}",signal_date=d.date().isoformat(),canonical_score=90-10*j,label_available_at=(d+timedelta(days=370)).isoformat(),hit_10x=(j==0 or (j==1 and i%2==0)),outcome_hash="a"*64,snapshot_expected_count=5,features={feature:dict(value=float(j+i%3),available_at=d.isoformat(),source_ref="fixture")}))
    return dict(schema=SCHEMA,source_run_id="WF5TEST",feature_names=[feature],rows=rows)

def run(d):
    return experiment(d,cutoff="2026-10-08",k=2,min_train=35,min_test=15,min_test_dates=3,min_positive=4)

def test_challenger_oos_and_no_promotion():
    result=run(sample())
    assert result["training_rows"]>=35
    assert result["metrics"]["dates_evaluated"]>=3
    assert result["training_latest_label_available_at"][:10]<result["first_oos_date"]
    assert not result["production_promotion_allowed"]
    assert result["report_sha256"]==run(sample())["report_sha256"]

def test_feature_future_leakage():
    d=sample()
    d["rows"][0]["features"]["D01"]["available_at"]="2030-01-01T00:00:00+00:00"
    with pytest.raises(ValueError,match="Lookahead"):run(d)

def test_immature_labels_block():
    d=sample()
    d["rows"][0]["label_available_at"]="2030-01-01T00:00:00+00:00"
    with pytest.raises(ValueError,match="immature"):run(d)

def test_missing_snapshot_member_rejected():
    d=sample();d["rows"].pop()
    with pytest.raises(ValueError,match="Incomplete labelled"):run(d)

def test_historical_label_proxy_rejected():
    with pytest.raises(ValueError,match="Feature allowlist"):run(sample("H10"))

def test_nan_and_missing_evidence_rejected():
    d=sample();d["rows"][0]["features"]["D01"]["value"]=float("nan")
    with pytest.raises(ValueError,match="Nonfinite"):run(d)
    d=sample();d["rows"][0]["features"]["D01"]["source_ref"]=""
    with pytest.raises(ValueError,match="authoritative source"):run(d)

def test_duplicate_rejected():
    d=sample();d["rows"].append(dict(d["rows"][0]))
    with pytest.raises(ValueError,match="Duplicate"):run(d)

def test_future_train_labels_purged():
    d=sample()
    first=run(d)["first_oos_date"]
    for row in d["rows"]:
        if row["signal_date"]<first:
            row["label_available_at"]="2026-09-01T00:00:00+00:00"
    with pytest.raises(ValueError,match="Not enough matured"):run(d)

def test_no_one_class_training():
    d=sample()
    for row in d["rows"]:row["hit_10x"]=True
    with pytest.raises(ValueError,match="Not enough matured|one class"):run(d)
