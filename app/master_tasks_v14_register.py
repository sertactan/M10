"""Validate V14 without losing any of the 14 V13 acceptance gates."""
from __future__ import annotations

import json
from pathlib import Path

from app.master_tasks_v12_register import validate_register


def validate_v14(path: Path, v13_path: Path) -> dict:
    result = validate_register(path)
    old = json.loads(v13_path.read_text(encoding="utf-8"))
    new = json.loads(path.read_text(encoding="utf-8"))
    old_gates = {c["id"]: c for t in old["tasks"] for c in t["criteria"]}
    new_gates = {c["id"]: c for t in new["tasks"] for c in t["criteria"]}
    if set(old_gates) != set(new_gates) or len(new_gates) != 40:
        raise ValueError("V13_GATE_INVENTORY_CHANGED")
    for key, gate in old_gates.items():
        if gate["verified"] and not new_gates[key]["verified"]:
            raise ValueError(f"V13_VERIFIED_GATE_REGRESSED:{key}")
    if sum(g["verified"] for g in old_gates.values()) != 14:
        raise ValueError("V13_CHECKPOINT_NOT_14")
    if result["verified_criteria"] < 14:
        raise ValueError("V13_ACCEPTANCE_BASELINE_REGRESSED")
    required = {"decision", "contract_test", "dependencies", "real_source",
                "missing_mandatory_input", "source_time_status", "independent_test",
                "private_receipt", "receipt_sha256", "human_approval_status"}
    for key, gate in new_gates.items():
        audit = gate.get("v14_audit")
        if not isinstance(audit, dict) or not required <= audit.keys():
            raise ValueError(f"V14_AUDIT_INCOMPLETE:{key}")
        if audit["decision"] != ("VERIFIED" if gate["verified"] else "OPEN"):
            raise ValueError(f"V14_AUDIT_DECISION_MISMATCH:{key}")
        if not audit["real_source"] or not audit["source_time_status"] or not audit["independent_test"]:
            raise ValueError(f"V14_AUDIT_EVIDENCE_INCOMPLETE:{key}")
        digest = audit["receipt_sha256"]
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError(f"V14_AUDIT_RECEIPT_HASH_INVALID:{key}")
    return result
