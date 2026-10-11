"""Validate the persistent V12 acceptance register without promoting scores."""
from __future__ import annotations

import json
from pathlib import Path

STATUSES = {"DONE", "PARTIAL", "BLOCKED", "PENDING_APPROVAL", "REVIEW_REQUIRED"}


def validate_register(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    tasks = data["tasks"]
    if [task["id"] for task in tasks] != list(range(9, 19)):
        raise ValueError("MASTER_TASK_IDS_MUST_BE_9_TO_18")
    log = data.get("work_log")
    if not isinstance(log, dict) or set(log) != {str(i) for i in range(9, 19)}:
        raise ValueError("EVERY_MASTER_TASK_NEEDS_A_WORK_LOG")
    required_log = {"completed", "code_action", "external_block", "human_decision",
                    "receipt", "acceptance_test"}
    for record in log.values():
        if not isinstance(record, dict) or any(not record.get(k) for k in required_log):
            raise ValueError("INCOMPLETE_TASK_WORK_LOG")
    seen = set()
    baseline = verified = done = 0
    for task in tasks:
        if task["status"] not in STATUSES or not task["criteria"]:
            raise ValueError("INVALID_TASK_STATUS_OR_EMPTY_CRITERIA")
        if not task["dependencies"] or not task["next_step"]:
            raise ValueError("DEPENDENCY_AND_NEXT_STEP_REQUIRED")
        for criterion in task["criteria"]:
            key = criterion["id"]
            if key in seen or not key.startswith(str(task["id"]) + "."):
                raise ValueError("DUPLICATE_OR_WRONG_CRITERION_ID")
            seen.add(key)
            if criterion["baseline_verified"] and not criterion["verified"]:
                raise ValueError("BASELINE_CRITERION_REGRESSED")
            if criterion["verified"] and (not criterion["evidence"] or not criterion["test"]):
                raise ValueError("VERIFIED_CRITERION_NEEDS_EVIDENCE_AND_TEST")
            baseline += bool(criterion["baseline_verified"])
            verified += bool(criterion["verified"])
        complete = all(c["verified"] for c in task["criteria"])
        if (task["status"] == "DONE") != complete:
            raise ValueError("DONE_REQUIRES_ALL_CRITERIA_AND_VICE_VERSA")
        done += complete
    return {"done_tasks": done, "task_count": len(tasks),
            "baseline_verified_criteria": baseline,
            "verified_criteria": verified,
            "total_criteria": len(seen),
            "newly_verified_criteria": verified - baseline,
            "statuses": {status: sum(t["status"] == status for t in tasks)
                         for status in sorted(STATUSES)}}
