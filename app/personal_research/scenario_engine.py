"""Evidence-bound alternatives; no statistically implied confidence intervals."""
from __future__ import annotations

from .contracts import digest


def validate_scenario(scenario: dict, evidence_ids: set[str]) -> dict:
    ids = scenario.get("evidence_ids")
    if not isinstance(ids, list) or not ids or not set(ids).issubset(evidence_ids):
        raise ValueError("Scenario requires referenced, verified evidence IDs")
    if not scenario.get("assumption") or not scenario.get("method_version"):
        raise ValueError("Scenario assumption and method version required")
    result = dict(scenario)
    result["numeric_result_type"] = "SCENARIO"
    result["historical_pit_accepted"] = False
    result["canonical_accepted"] = False
    result["receipt_sha256"] = digest(result)
    return result
