from __future__ import annotations

"""CLI for offline, noncanonical Learning V3 challenger experiments.

Never uploads user dataset to public GitHub, modifies S15/S16, deploys
weights, or executes a trading strategy. Runs only when explicitly called.
"""
import argparse
import json
from pathlib import Path
from core.learning_v3.challenger import experiment


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset",type=Path,required=True)
    p.add_argument("--cutoff",required=True)
    p.add_argument("--k",type=int,default=10)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--min-train",type=int,default=100)
    p.add_argument("--min-test",type=int,default=40)
    p.add_argument("--min-test-dates",type=int,default=3)
    p.add_argument("--min-positive",type=int,default=8)
    args=p.parse_args()
    try:
        if not args.dataset.is_file():
            raise ValueError("PIT evidence dataset does not exist")
        if args.out.exists():
            raise ValueError("Refusing to overwrite an existing immutable experiment report")
        data=json.loads(args.dataset.read_text(encoding="utf-8"))
        result=experiment(data,cutoff=args.cutoff,k=args.k,
                          min_train=args.min_train,min_test=args.min_test,
                          min_test_dates=args.min_test_dates,min_positive=args.min_positive)
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False)+"\n",
                            encoding="utf-8")
        print(json.dumps({"status":result["status"],"out":str(args.out),
                          "train":result["training_rows"],
                          "oos":result["test_rows"],
                          "precision_delta_pp":result["metrics"]["precision_delta_pp"],
                          "production_promotion_allowed":False},ensure_ascii=False))
    except (OSError,ValueError,TypeError,KeyError,json.JSONDecodeError) as exc:
        p.exit(2,"LEARNING_V3_EXPERIMENT_BLOCKED: "+str(exc)+"\n")


if __name__=="__main__":
    main()
