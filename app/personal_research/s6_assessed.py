"""Personal S6 source matrix and RSST diagnostic using frozen calculator gates."""
from __future__ import annotations

from datetime import datetime

from app.recovered_dechow import calculate_dechow, REQUIRED, SOURCE_SHA256
from .contracts import personal_result


def assess_s6(periods: list[dict], as_of: datetime, *, original_status="N/A",
              source_rsst=None, expert_decomposition=None, expert_issuance=None) -> dict:
    """Call existing frozen engine, never manufacture approved reviewer fields.

    Personal accounting scenarios may be displayed as alternatives but cannot
    cause an originally restricted calculator to assert a completed S6 score.
    """
    original = calculate_dechow(
        periods, as_of=as_of, decomposition_review=expert_decomposition,
        issuance_review=expert_issuance)
    coverage = []
    for index, period in enumerate(periods if isinstance(periods, list) else []):
        facts = period.get("facts", {}) if isinstance(period, dict) else {}
        coverage.append({"fy": period.get("end"),
                         "present": sorted(set(facts) & set(REQUIRED)),
                         "missing": sorted(set(REQUIRED) - set(facts))})
    components = {"frozen_calculator": original.get("components", {}),
                  "frozen_contract_sha256": SOURCE_SHA256,
                  "mandatory_input_matrix": coverage,
                  "diagnostic_rsst": source_rsst,
                  "frozen_evidence_sha256": original.get("evidence_hash")}
    if original.get("score") is not None:
        outcome = personal_result(
            "S6", score=original["score"], numeric_result_type="EXACT",
            original_status=original_status, components=components,
            evidence=original.get("evidence", {}).get("inputs", []),
            status="DERIVED_FROM_EXACT_SOURCES")
    else:
        outcome = personal_result("S6", original_status=original_status,
                                  components=components, missing=original["missing"])
    outcome["source_review_status"] = (
        "ORIGINAL_REVIEWED_SOURCE" if original.get("score") is not None
        else "PERSONAL_DIAGNOSTIC_UNRESOLVED")
    return outcome
