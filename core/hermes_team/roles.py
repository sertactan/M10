"""Six logical roles; default execution is local deterministic Python."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Role:
    code: str
    title: str
    mode: str
    capability: str


ROLES = (
    Role("A1", "Chief Strategist", "llm_optional", "plan_and_approve_research"),
    Role("A2", "Market Discovery", "python_first", "screen_pit_universe"),
    Role("A3", "Fundamental Analyst", "python_first", "analyze_sec_s153"),
    Role("A4", "Catalyst S16-EA", "llm_optional", "classify_verified_news"),
    Role("A5", "Risk and Data Validator", "python_only", "fail_closed_risk"),
    Role("A6", "Learning and Performance Auditor", "python_first", "walk_forward_audit"),
)
ROLE_BY_CODE = {r.code: r for r in ROLES}


def route(task: str, *, allow_llm: bool = False) -> dict:
    mapping = {"strategy": "A1", "scan": "A2", "fundamental": "A3",
               "catalyst": "A4", "risk": "A5", "learning": "A6"}
    code = mapping.get(task)
    if code is None:
        return {"status": "INCONCLUSIVE", "reason": "UNKNOWN_TASK"}
    role = ROLE_BY_CODE[code]
    return {"role": code, "capability": role.capability,
            "execution": "LLM_GATEWAY" if role.mode != "python_only"
            and allow_llm else "PYTHON_OR_REVIEW",
            "status": "PLANNED_NOT_EXECUTED"}
