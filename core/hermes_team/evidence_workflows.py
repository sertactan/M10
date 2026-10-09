"""Offline evidence-producing M10 workflows, not model-generated financial scores.

All child scripts already exist in M10. No broker operations or model training.
Outputs are bounded to source counts and their documented fail-closed blockers.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

AUDITS = {
    "strategy": "scripts.phase25i_real_market_gate_matrix",
    "risk": "scripts.phase25i_real_market_gate_matrix",
    "learning": "scripts.phase25i_real_market_gate_matrix",
    "scan": "scripts.phase25j_p1_sec_issuer_and_p2p3_source_triage",
    "fundamental": "scripts.phase25j_p1_sec_issuer_and_p2p3_source_triage",
}
M10_SOURCE_ROOT = Path(__file__).resolve().parents[2]


def perform_local_evidence_task(task: str) -> dict:
    if task == "catalyst":
        return {"status": "INCONCLUSIVE", "reason": "NO_VERIFIED_TIMESTAMPED_CATALYST",
                "llm_called": False, "real_market_alert_emitted": False}
    module = AUDITS.get(task)
    if module is None:
        return {"status": "INCONCLUSIVE", "reason": "UNKNOWN_TASK", "llm_called": False}
    try:
        proc = subprocess.run([sys.executable, "-m", module], cwd=M10_SOURCE_ROOT, capture_output=True,
                              text=True, encoding="utf-8", errors="replace",
                              timeout=90, check=False)
        result = json.loads(proc.stdout)
        if not isinstance(result, dict) or "status" not in result:
            raise ValueError("NOT_A_REPORT")
        if task in ("strategy", "risk", "learning"):
            # Strategy may coordinate source-gathering specialists even when
            # the final investment/backtest decision is blocked.
            return {
                "status": "INCONCLUSIVE" if task == "strategy" else result["status"],
                "source_status": result["status"],
                "blockers": result.get("blockers", []),
                "walk_forward_executed": result.get("walk_forward_executed", False),
                "Learning_V3_executed": result.get("Learning_V3_executed", False),
                "db_modified": result.get("db_modified"),
                "source": "M10_PHASE25I_LOCAL_READONLY",
                "process_exit_code": proc.returncode,
                "llm_called": False,
            }
        return {
            "status": result["status"],
            "p1_issuer_documents": result.get("p1_SEC_issuer_CIK_document_refs"),
            "candidate_count": result.get("other_distinct_SimFinIds"),
            "source_event_rows": result.get("other_source_event_rows"),
            "canonical_eligible": result.get("canonical_eligible"),
            "source": "M10_PHASE25J_EXISTING_LOCAL_RESEARCH_REPORTS",
            "process_exit_code": proc.returncode,
            "llm_called": False,
            "canonical_backtest_allowed": False,
        }
    except (OSError, ValueError, TypeError, subprocess.TimeoutExpired):
        return {"status": "INCONCLUSIVE", "reason": "EXISTING_M10_AUDIT_UNAVAILABLE",
                "source": module, "llm_called": False}
