"""Check V13 gate evidence and preserve every verified V12 gate."""
from __future__ import annotations

import json
from pathlib import Path

from app.master_tasks_v12_register import validate_register


def validate_v13(path: Path, v12_path: Path) -> dict:
    result = validate_register(path)
    old = json.loads(v12_path.read_text(encoding="utf-8"))
    new = json.loads(path.read_text(encoding="utf-8"))
    old_gates = {c["id"]: c for t in old["tasks"] for c in t["criteria"]}
    new_gates = {c["id"]: c for t in new["tasks"] for c in t["criteria"]}
    if set(old_gates) != set(new_gates):
        raise ValueError("V12_GATE_INVENTORY_CHANGED")
    for key, gate in old_gates.items():
        if gate["verified"] and not new_gates[key]["verified"]:
            raise ValueError(f"V12_VERIFIED_GATE_REGRESSED:{key}")
    if result["verified_criteria"] < 13 or result["total_criteria"] != 40:
        raise ValueError("V12_ACCEPTANCE_BASELINE_REGRESSED")
    return result
