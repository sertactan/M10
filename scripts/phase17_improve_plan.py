from __future__ import annotations

"""V3 'geliştir' planner: inspect evidence, emit bounded PR backlog.

This is a plan generator, not an autonomous source-code mutator. Owner review,
CI and protected canonical source files remain required. No network or market
data access in this module.
"""
import json
from pathlib import Path

PRIORITIES = ("P0","P1","P2")
PROTECTED = (
    "specs/", "skills/meridyen-equity-research/references/models/",
    "core/models/s153_v141.py", "core/models/s153_v14.py",
    "core/models/s16", "core/backtest/outcomes.py",
)


def plan(*,experiment_report=None,phase14=None,phase15=None,phase16=None):
    issues=[]
    def add(pri,code,explanation,fix):
        issues.append(dict(priority=pri,code=code,
                           explanation=explanation,proposed_fix=fix,
                           protected_model_edits_allowed=False))
    if not phase14 or phase14.get("status") not in (
            "PREFLIGHT_INPUT_COVERAGE_ASSERTED_NOT_PIT_CERTIFIED",):
        add("P0","PIT_UNIVERSE_NOT_AUDITED",
            "144 historical month-end PIT coverage not independently validated",
            "Complete historical prices/universe/filing availability and get independent audit")
    if not phase15 or phase15.get("status")!="OOS_RESEARCH_DIAGNOSTIC_NOT_PIT_CERTIFIED":
        add("P0","OOS_SOURCE_UNAVAILABLE",
            "No complete source-hashed WF6/WF5 OOS cohort report",
            "Run Phase15 against complete mature source evidence")
    if experiment_report:
        if experiment_report.get("schema")!="MERIDYEN_LEARNING_V3_EXPERIMENT_V1":
            raise ValueError("Unrecognized experiment schema")
        if experiment_report.get("production_promotion_allowed") is not False:
            raise ValueError("Unsafe challenger claims production promotion")
        m=experiment_report.get("metrics") or {}
        diff=m.get("precision_delta_pp")
        if diff is None or diff<=0:
            add("P1","CHALLENGER_NOT_BETTER",
                "Candidate failed to beat frozen S15 on available OOS Precision@K",
                "Review feature PIT, sample size, OOS regimes and controls without modifying canonical formulas")
        else:
            add("P1","CHALLENGER_NEEDS_INDEPENDENT_REPLICATION",
                "Single-split positive OOS delta is not independent proof",
                "Repeat on multiple untouched time regimes with matched controls and trading costs")
        add("P2","EXPERIMENT_MANIFEST_REVIEW",
            "Experiment output is research only, not signed release",
            "Archive hashed data manifest and experiment with reviewer signoff")
    else:
        add("P1","NO_LEARNING_V3_EXPERIMENT",
            "No successful dated-feature OOS challenger experiment",
            "Export complete mature PIT feature dataset and run Phase17 CLI")
    if not phase16 or phase16.get("cloud_status") not in ("CLOUD_ROUNDTRIP_VERIFIED",):
        add("P1","BACKUP_RESTORE_NOT_PROVEN",
            "No independently verified cloud roundtrip and restore receipt",
            "Configure Windows rclone crypt and test new-file disaster restore")
    return {
        "schema":"MERIDYEN_V3_IMPROVEMENT_PLAN_V1",
        "status":"REVIEW_REQUIRED_NO_AUTONOMOUS_CODE_WRITE",
        "issues":sorted(issues,key=lambda i:(PRIORITIES.index(i["priority"]),i["code"])),
        "allowed_next_change":"NONCANONICAL_ONLY_VIA_PR_AND_PYTHON_CI",
        "approved_model_promotion":False,
        "auto_merge":False,"trade_execution":False,
        "protected_paths":list(PROTECTED),
        "rollback":"Revert reviewed noncanonical PR using git revert; never rewrite frozen S15/S16 in place",
    }


def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--experiment",type=Path)
    p.add_argument("--phase14",type=Path)
    p.add_argument("--phase15",type=Path)
    p.add_argument("--phase16",type=Path)
    p.add_argument("--out",required=True,type=Path)
    args=p.parse_args()
    try:
        def read(path):
            return json.loads(path.read_text(encoding="utf-8")) if path else None
        result=plan(experiment_report=read(args.experiment),
                    phase14=read(args.phase14),phase15=read(args.phase15),
                    phase16=read(args.phase16))
        if args.out.exists():
            raise ValueError("Refusing overwrite of prior improvement plan")
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
        print(json.dumps({"status":result["status"],"findings":len(result["issues"]),
                          "output":str(args.out),"auto_merge":False},ensure_ascii=False))
    except (OSError,ValueError,json.JSONDecodeError) as exc:
        p.exit(2,"PHASE17_IMPROVE_BLOCKED: "+str(exc)+"\n")


if __name__=="__main__":
    main()
